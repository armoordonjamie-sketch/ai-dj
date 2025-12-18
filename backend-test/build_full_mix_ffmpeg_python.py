"""build_full_mix_ffmpeg_python.py

Full-length DJ-style mix with a crossfade + TTS ducking, using ffmpeg-python.

What it does:
  - Plays song A from start.
  - Crossfades into song B over `--crossfade` seconds (no trimming; full tracks).
  - Starts a TTS clip `--tts-lead` seconds before the crossfade starts.
  - Ducks the music under the TTS using FFmpeg's `sidechaincompress`.

Requirements:
  - pip install ffmpeg-python
  - ffmpeg + ffprobe available on PATH

Example (PowerShell):
  python build_full_mix_ffmpeg_python.py `
    --song-a "Taylor Swift - Blank Space.mp3" `
    --song-b "Taylor Swift - Bad Blood.mp3" `
    --tts "tts_0a659255.mp3" `
    --crossfade 8 `
    --tts-lead 2 `
    --out "test_mix.mp3" `
    --debug
"""

from __future__ import annotations

import argparse
import os
from typing import Any, Dict

import ffmpeg


def _probe_duration(path: str) -> float:
    """Duration in seconds using ffprobe (via ffmpeg-python)."""
    info: Dict[str, Any] = ffmpeg.probe(path)
    # Prefer format.duration (most common)
    dur = info.get('format', {}).get('duration', None)
    if dur is not None:
        return float(dur)

    # Fallback: max stream duration
    durs = []
    for s in info.get('streams', []):
        if 'duration' in s and s['duration'] is not None:
            try:
                durs.append(float(s['duration']))
            except ValueError:
                pass
    if not durs:
        raise RuntimeError(f"Could not determine duration for: {path}")
    return max(durs)


def build_mix(
    song_a: str,
    song_b: str,
    tts: str,
    out_path: str,
    crossfade_sec: float = 8.0,
    tts_lead_sec: float = 2.0,
    sample_rate: int = 48000,
    # Ducking params (tweak to taste)
    threshold: float = 0.03,
    ratio: float = 10.0,
    attack_ms: float = 10.0,
    release_ms: float = 300.0,
    voice_gain_db: float = 0.0,
    music_gain_db: float = 0.0,
    mp3_q: int = 2,
    debug: bool = False,
) -> None:
    for p in (song_a, song_b, tts):
        if not os.path.exists(p):
            raise FileNotFoundError(p)

    dur_a = _probe_duration(song_a)
    dur_b = _probe_duration(song_b)

    # acrossfade needs both inputs >= crossfade
    cf = max(0.05, float(crossfade_sec))
    cf = min(cf, max(0.05, dur_a - 0.05), max(0.05, dur_b - 0.05))

    transition_start = max(0.0, dur_a - cf)
    tts_start = max(0.0, transition_start - max(0.0, float(tts_lead_sec)))
    out_dur = max(0.05, dur_a + dur_b - cf)

    if debug:
        print(f"dur_a={dur_a:.3f}s  dur_b={dur_b:.3f}s")
        print(f"crossfade={cf:.3f}s  transition_start={transition_start:.3f}s")
        print(f"tts_start={tts_start:.3f}s  out_dur={out_dur:.3f}s")

    # Inputs
    in_a = ffmpeg.input(song_a)
    in_b = ffmpeg.input(song_b)

    # IMPORTANT: use itsoffset to place voice in the timeline.
    # Do NOT reset PTS to zero after this, or you'll lose the offset.
    in_voice = ffmpeg.input(tts, itsoffset=tts_start)

    # Normalize / align formats for stable filtering
    a = (
        in_a.audio
        .filter('aresample', sample_rate)
        .filter('aformat', sample_fmts='fltp', channel_layouts='stereo')
        .filter('asetpts', 'PTS-STARTPTS')
    )
    b = (
        in_b.audio
        .filter('aresample', sample_rate)
        .filter('aformat', sample_fmts='fltp', channel_layouts='stereo')
        .filter('asetpts', 'PTS-STARTPTS')
    )

    # Crossfade full tracks
    music = ffmpeg.filter([a, b], 'acrossfade', d=cf, c1='tri', c2='tri')

    if music_gain_db != 0.0:
        music = music.filter('volume', f"{music_gain_db}dB")

    # Voice: resample + ensure stereo; keep PTS (offset by itsoffset)
    voice = (
        in_voice.audio
        .filter('aresample', sample_rate)
        .filter('aformat', sample_fmts='fltp', channel_layouts='stereo')
    )
    if voice_gain_db != 0.0:
        voice = voice.filter('volume', f"{voice_gain_db}dB")

    # We use the voice stream twice (sidechain + final mix).
    # ffmpeg-python requires an explicit split when one stream feeds
    # multiple downstream filters.
    voice_split = voice.filter_multi_output('asplit', 2)
    voice_sc = voice_split.stream(0)
    voice_mix = voice_split.stream(1)

    # Make a sidechain signal that lasts as long as the music output.
    # apad pads with silence after voice ends; then we trim to full output duration.
    sc = voice_sc.filter('apad').filter('atrim', duration=out_dur)

    # Duck the music whenever voice is present
    ducked = ffmpeg.filter(
        [music, sc],
        'sidechaincompress',
        threshold=threshold,
        ratio=ratio,
        attack=attack_ms,
        release=release_ms,
    )

    # Mix voice on top
    mixed = ffmpeg.filter(
        [ducked, voice_mix],
        'amix',
        inputs=2,
        duration='first',
        dropout_transition=0,
    ).filter('atrim', duration=out_dur)

    ext = os.path.splitext(out_path)[1].lower()
    if ext == '.wav':
        out_kwargs = {'c:a': 'pcm_s16le'}
    elif ext == '.flac':
        out_kwargs = {'c:a': 'flac'}
    else:
        # Default: MP3 VBR quality mode
        out_kwargs = {'c:a': 'libmp3lame', 'q:a': mp3_q}

    stream = ffmpeg.output(mixed, out_path, **out_kwargs).overwrite_output()

    if debug:
        print('FFmpeg command:')
        print('  ' + ' '.join(stream.compile()))

    # Run and surface stderr on failure
    try:
        stream.run(capture_stdout=True, capture_stderr=True)
    except ffmpeg.Error as e:
        raise RuntimeError(
            "FFmpeg failed. Full stderr:\n" + (e.stderr.decode('utf-8', errors='replace') if e.stderr else '')
        ) from e


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--song-a', required=True)
    ap.add_argument('--song-b', required=True)
    ap.add_argument('--tts', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--crossfade', type=float, default=8.0)
    ap.add_argument('--tts-lead', type=float, default=2.0)
    ap.add_argument('--threshold', type=float, default=0.03)
    ap.add_argument('--ratio', type=float, default=10.0)
    ap.add_argument('--attack-ms', type=float, default=10.0)
    ap.add_argument('--release-ms', type=float, default=300.0)
    ap.add_argument('--voice-gain-db', type=float, default=0.0)
    ap.add_argument('--music-gain-db', type=float, default=0.0)
    ap.add_argument('--mp3-q', type=int, default=2)
    ap.add_argument('--debug', action='store_true')
    args = ap.parse_args()

    build_mix(
        song_a=args.song_a,
        song_b=args.song_b,
        tts=args.tts,
        out_path=args.out,
        crossfade_sec=args.crossfade,
        tts_lead_sec=args.tts_lead,
        threshold=args.threshold,
        ratio=args.ratio,
        attack_ms=args.attack_ms,
        release_ms=args.release_ms,
        voice_gain_db=args.voice_gain_db,
        music_gain_db=args.music_gain_db,
        mp3_q=args.mp3_q,
        debug=args.debug,
    )
    print(f"Rendered mix -> {args.out}")


if __name__ == '__main__':
    main()
