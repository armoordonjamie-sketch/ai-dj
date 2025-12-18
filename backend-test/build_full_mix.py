"""
Build a *full-length* DJ-style mix:
- Play song A from the beginning.
- Crossfade into song B near the end of song A.
- Play song B to the end.
- Overlay a TTS "DJ talk" just before the transition, while ducking the music under the voice.

Requires: ffmpeg + ffprobe on PATH.

Usage:
  python build_full_mix.py --song-a "SongA.mp3" --song-b "SongB.mp3" --tts "tts.mp3" \
    --crossfade 8 --tts-lead 2 --out "test_mix.mp3"
"""
from __future__ import annotations

import argparse
import os
import subprocess
from typing import Optional


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True)


def _validate_inputs(*paths: str) -> None:
    missing = [p for p in paths if not os.path.exists(p)]
    if missing:
        raise FileNotFoundError(f"Missing input files: {missing}")


def ffprobe_duration_seconds(path: str) -> float:
    """Return media duration in seconds (float) using ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path,
    ]
    res = _run(cmd)
    if res.returncode != 0:
        raise RuntimeError(f"ffprobe failed ({res.returncode}):\n{res.stderr}")
    try:
        return float(res.stdout.strip())
    except ValueError as e:
        raise RuntimeError(f"Could not parse ffprobe duration from: {res.stdout!r}") from e


def build_full_mix(
    song_a: str,
    song_b: str,
    tts: str,
    out_path: str,
    crossfade_sec: float = 8.0,
    tts_lead_sec: float = 2.0,
    tts_threshold: float = 0.05,
    tts_ratio: float = 8.0,
    tts_attack_ms: float = 5.0,
    tts_release_ms: float = 250.0,
    sample_rate: int = 48000,
) -> str:
    """
    Render out_path with:
      output_len = dur(A) + dur(B) - crossfade
      transition starts at dur(A) - crossfade
      tts starts at (transition_start - tts_lead)
    """
    _validate_inputs(song_a, song_b, tts)

    dur_a = ffprobe_duration_seconds(song_a)
    dur_b = ffprobe_duration_seconds(song_b)

    # Guardrails: acrossfade requires both inputs to be >= crossfade.
    cf = max(0.05, float(crossfade_sec))
    cf = min(cf, max(0.05, dur_a - 0.05), max(0.05, dur_b - 0.05))

    transition_start = max(0.0, dur_a - cf)
    tts_start = max(0.0, transition_start - max(0.0, float(tts_lead_sec)))
    delay_ms = int(round(tts_start * 1000.0))

    out_dur = max(0.05, dur_a + dur_b - cf)

    # We avoid apad=whole_dur for compatibility; instead we build a "sidechain bed"
    # by mixing delayed voice into a full-length silence stream.
    filtergraph = (
        f"[0:a]aresample={sample_rate}:async=1,aformat=sample_fmts=fltp:channel_layouts=stereo[a];"
        f"[1:a]aresample={sample_rate}:async=1,aformat=sample_fmts=fltp:channel_layouts=stereo[b];"
        f"[a][b]acrossfade=d={cf}:c1=tri:c2=tri[music];"

        f"[2:a]aresample={sample_rate}:async=1,aformat=sample_fmts=fltp:channel_layouts=stereo,"
        f"adelay={delay_ms}|{delay_ms}[voice];"

        f"anullsrc=r={sample_rate}:cl=stereo:d={out_dur}[sil];"
        f"[sil][voice]amix=inputs=2:duration=first:dropout_transition=0[sc];"

        f"[music][sc]sidechaincompress=threshold={tts_threshold}:ratio={tts_ratio}:"
        f"attack={tts_attack_ms}:release={tts_release_ms}[ducked];"

        f"[ducked][voice]amix=inputs=2:duration=first:dropout_transition=0,"
        f"atrim=duration={out_dur}[out]"
    )

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-i", song_a,
        "-i", song_b,
        "-i", tts,
        "-filter_complex", filtergraph,
        "-map", "[out]",
        "-c:a", "libmp3lame",
        "-q:a", "2",
        out_path,
    ]

    res = _run(cmd)
    if res.returncode != 0:
        raise RuntimeError(
            "ffmpeg failed.\n"
            f"Command:\n  {' '.join(cmd)}\n\n"
            f"stderr:\n{res.stderr}"
        )

    return out_path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--song-a", required=True)
    ap.add_argument("--song-b", required=True)
    ap.add_argument("--tts", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--crossfade", type=float, default=8.0, help="Seconds of overlap between end of A and start of B.")
    ap.add_argument("--tts-lead", type=float, default=2.0, help="Start TTS this many seconds before transition start.")
    args = ap.parse_args()

    out = build_full_mix(
        song_a=args.song_a,
        song_b=args.song_b,
        tts=args.tts,
        out_path=args.out,
        crossfade_sec=args.crossfade,
        tts_lead_sec=args.tts_lead,
    )
    print(f"Rendered mix -> {out}")


if __name__ == "__main__":
    main()
