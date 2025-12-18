"""Standalone test mix builder using only ffmpeg (no backend imports).

Inputs (placed in backend-test/):
- Taylor Swift - Blank Space.mp3   (song A)
- Taylor Swift - Bad Blood.mp3     (song B)
- tts_0a659255.mp3                 (DJ talk)

Output: backend-test/test_mix.mp3
"""
import os
import subprocess
from typing import List

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
SONG_A = os.path.join(BASE_DIR, "Taylor Swift - Blank Space.mp3")
SONG_B = os.path.join(BASE_DIR, "Taylor Swift - Bad Blood.mp3")
TTS = os.path.join(BASE_DIR, "tts_0a659255.mp3")
OUTPUT = os.path.join(BASE_DIR, "test_mix.mp3")


def _validate_inputs(paths: List[str]) -> None:
    """Ensure required files exist before rendering."""
    missing = [p for p in paths if not os.path.exists(p)]
    if missing:
        raise FileNotFoundError(f"Missing input files: {missing}")


def build_test_mix(duration_sec: float = 90.0, crossfade_sec: float = 8.0) -> str:
    """Render a single MP3 with crossfade + TTS ducking using raw ffmpeg."""
    _validate_inputs([SONG_A, SONG_B, TTS])

    cf = min(crossfade_sec, max(1.0, duration_sec / 4))  # guardrails

    filtergraph = (
        f"[0:a]atrim=start=0:duration={duration_sec},asetpts=PTS-STARTPTS,"
        f"aresample=48000:async=1,aformat=sample_fmts=s16:channel_layouts=stereo[a];"
        f"[1:a]atrim=start=0:duration={duration_sec},asetpts=PTS-STARTPTS,"
        f"aresample=48000:async=1,aformat=sample_fmts=s16:channel_layouts=stereo[b];"
        f"[a]afade=t=out:st={duration_sec-cf}:d={cf}[a_f];"
        f"[b]afade=t=in:st=0:d={cf}[b_f];"
        f"[a_f][b_f]amix=inputs=2:duration=longest:dropout_transition=0[music];"
        # IMPORTANT:
        # - sidechaincompress OUTPUTS ONLY the ducked music (it does NOT include TTS audio).
        # - sidechaincompress can stop early when the sidechain ends.
        # So we pad TTS with silence to at least duration_sec, split it for sidechain+mix,
        # then mix TTS over the ducked music.
        f"[2:a]atrim=start=0,asetpts=PTS-STARTPTS,"
        f"aresample=48000:async=1,aformat=sample_fmts=s16:channel_layouts=stereo,"
        f"apad=whole_dur={duration_sec}[tts_pad];"
        f"[tts_pad]asplit=2[sc][voice];"
        f"[music][sc]sidechaincompress=threshold=0.05:ratio=8:attack=5:release=250[ducked];"
        f"[ducked][voice]amix=inputs=2:duration=longest:dropout_transition=0[out]"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        SONG_A,
        "-i",
        SONG_B,
        "-i",
        TTS,
        "-filter_complex",
        filtergraph,
        "-map",
        "[out]",
        "-t",
        str(duration_sec),
        "-c:a",
        "libmp3lame",
        "-q:a",
        "2",
        OUTPUT,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed ({result.returncode}):\n{result.stderr}")

    return OUTPUT


if __name__ == "__main__":
    path = build_test_mix(duration_sec=90.0, crossfade_sec=8.0)
    print(f"Rendered test mix -> {path}")

