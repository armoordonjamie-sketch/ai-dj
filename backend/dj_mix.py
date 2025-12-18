"""DJ Mix Engine using ffmpeg-python.

This module provides the core mixing functionality for the AI DJ system.
It handles loudness normalization, transition application, and TTS integration.

Adapted from v2.0 DJ mix engine - works with full audio files.
"""
import ffmpeg
import os
import json
import re
import logging
from typing import Optional, Dict, Any

from backend import transitions
from backend.config import SEGMENT_DIR

logger = logging.getLogger(__name__)

# Audio processing constants
TARGET_LUFS = -14.0  # Global streaming standard
SAMPLE_RATE = 44100
TTS_DUCK_VOLUME = 0.45  # Music level during DJ talk (matches tests)


def get_loudness(file_path: str) -> float:
    """
    Measure the Integrated Loudness (LUFS) of an audio file.
    
    Uses FFmpeg's loudnorm filter to analyze the audio file
    and extract the integrated loudness value.
    
    Args:
        file_path: Path to the audio file
        
    Returns:
        Integrated loudness in LUFS (e.g., -10.5)
        Returns -14.0 as fallback on error
    """
    try:
        logger.info(f"Measuring loudness: {file_path}...")
        _, err = (
            ffmpeg
            .input(file_path)
            .filter('loudnorm', print_format='json')
            .output('-', format='null')
            .run(capture_stdout=True, capture_stderr=True)
        )
        
        output_str = err.decode('utf-8')
        json_match = re.search(r'\{[\s\S]*\}', output_str)
        if json_match:
            stats = json.loads(json_match.group(0))
            lufs = float(stats['input_i'])
            logger.info(f"  - Measured: {lufs} LUFS")
            return lufs
    except Exception as e:
        logger.error(f"  - Error measuring {file_path}: {e}")
    return TARGET_LUFS  # Default fallback


def get_duration(file_path: str) -> float:
    """
    Get duration of an audio file in seconds.
    
    Args:
        file_path: Path to the audio file
        
    Returns:
        Duration in seconds
    """
    try:
        probe = ffmpeg.probe(file_path)
        return float(probe['format']['duration'])
    except Exception as e:
        logger.error(f"Failed to probe duration: {e}")
        return 210.0  # Default fallback


def normalize_stream(stream, current_lufs: float, target_lufs: float = TARGET_LUFS):
    """
    Apply a static gain to reach the target LUFS.
    
    Args:
        stream: ffmpeg-python audio stream
        current_lufs: Current loudness of the stream
        target_lufs: Target loudness (default: -14.0 LUFS)
        
    Returns:
        ffmpeg-python audio stream with volume adjustment applied
    """
    gain_db = target_lufs - current_lufs
    logger.info(f"  - Applying gain: {gain_db:.2f} dB to reach {target_lufs} LUFS")
    return stream.filter('volume', f"{gain_db}dB")


def create_dj_mix(
    song1_path: str,
    song2_path: str,
    transition_type: str = 'blend',
    output_path: Optional[str] = None,
    fast_test: bool = False,
    t_start: Optional[float] = None,
    xfade_dur: float = 10.0,
    tts_offset: float = 5.0,
    tts_path: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Create a TRANSITION SEGMENT between two songs with optional TTS.
    
    This creates a segment containing:
    - Last ~5s of Song A (lead-in for crossfade)
    - The transition itself (~10s crossfade)  
    - MOST of Song B (except last ~20s, leaving room for next transition)
    
    Each segment is ~3-4 minutes and contains one transition plus most of the next song.
    Segments are designed to play back-to-back for seamless audio.
    
    Args:
        song1_path: Path to the outgoing (Song A) audio file
        song2_path: Path to the incoming (Song B) audio file
        transition_type: One of 'blend', 'bass_swap', 'filter_sweep', 
                        'echo_out', 'vinyl_stop'
        output_path: Output file path (auto-generated if None)
        fast_test: If True, render short test snippet instead of full mix
        t_start: Transition start time in Song A (auto-calculated if None)
        xfade_dur: Crossfade duration in seconds
        tts_offset: Seconds before transition to start DJ voiceover
        tts_path: Path to TTS audio file (optional)
        
    Returns:
        Dict with output_path, metadata, and metadata_path on success, or None on error
    """
    # Generate output path if not provided
    if output_path is None:
        os.makedirs(SEGMENT_DIR, exist_ok=True)
        import uuid
        mix_id = uuid.uuid4().hex[:8]
        output_path = os.path.join(SEGMENT_DIR, f"mix_{mix_id}.mp3")
    
    # Get durations
    song1_duration = get_duration(song1_path)
    song2_duration = get_duration(song2_path)
    
    # Get TTS duration if provided
    tts_duration = 0.0
    if tts_path and os.path.exists(tts_path):
        tts_duration = get_duration(tts_path)
    
    # Calculate transition start if not provided
    crossfade_duration = xfade_dur
    tts_offset_before_transition = tts_offset

    transition_buffer = 20.0
    song_to_song_overlap = 0.75  # seconds of intentional overlap between segments
    song1_lead_in = 12.0  # Lead-in inside this segment before the transition

    transition_start = (
        t_start if t_start is not None
        else song1_duration - transition_buffer - crossfade_duration
    )
    
    # Ensure transition_start is valid
    if transition_start < 20:
        transition_start = 20
    if transition_start > song1_duration - crossfade_duration:
        transition_start = song1_duration - crossfade_duration

    # Measure loudness
    s1_lufs = get_loudness(song1_path)
    s2_lufs = get_loudness(song2_path)
    tts_lufs = get_loudness(tts_path) if tts_path and os.path.exists(tts_path) else TARGET_LUFS

    # ========== TRANSITION SEGMENT MODE ==========
    # We create a SHORT segment, not a full mix of both songs
    # 
    # Segment structure:
    # - Include last ~5s of song A (from transition_start - 5 to end of crossfade)
    # - Transition happens at position 5s in our segment  
    # - Include first ~45s of song B (after transition)
    #
    # The intro segment already played song A up to (song_duration - 25s).
    # So we only need a small lead-in to overlap/blend.
    #
    # Total segment: ~5 + crossfade + 45 ≈ 60 seconds
    
    # Start position in song A
    song1_start = max(0, transition_start - song1_lead_in)
    
    # How much of song A we're including (from song1_start to end of song A)
    song1_segment_duration = song1_duration - song1_start
    
    # Position of transition in our OUTPUT segment
    segment_transition_pos = transition_start - song1_start
    
    # How much of song B to include
    # Include MOST of song B (leave only ~20s for the NEXT segment's lead-in)
    # This ensures smooth continuity across segments without overlap
    
    # We want segment N to end exactly where segment N+1 starts
    # Segment N+1 starts at: transition_start (next) - lead_in
    # So we need to trim song B so it ends at that point
    
    # Next transition anchor in Song B (start of the next crossfade)
    song2_next_transition_start = song2_duration - transition_buffer
    song2_handoff_start = max(0.0, song2_next_transition_start - song1_lead_in)

    # Keep a known overlap with the next segment to avoid gaps
    song2_trim = min(song2_handoff_start + song_to_song_overlap, song2_duration)

    if song2_trim < 60:
        song2_trim = song2_duration  # Use full song if very short
    
    logger.info(f"--- [TRANSITION SEGMENT] Mode: {transition_type} ---")
    logger.info(f"Song A: {song1_segment_duration:.1f}s included (from {song1_start:.1f}s, transition at {transition_start:.1f}s)")
    logger.info(
        "Song B: %.1fs included (of %.1fs total) — handoff @ %.1fs with %.2fs overlap",
        song2_trim,
        song2_duration,
        song2_handoff_start,
        song_to_song_overlap,
    )
    
    # Input song A from the start position
    audio1_in = ffmpeg.input(song1_path, ss=song1_start).audio
    # Input song B from the beginning
    audio2_in = ffmpeg.input(song2_path).audio
    
    # Process Song A: include from song1_start to end
    a1 = audio1_in.filter('aresample', SAMPLE_RATE)
    a1 = a1.filter('atrim', duration=song1_segment_duration).filter('asetpts', 'PTS-STARTPTS')
    a1 = normalize_stream(a1, s1_lufs, target_lufs=TARGET_LUFS)
    
    # Process Song B: trim to song2_trim duration
    a2 = audio2_in.filter('aresample', SAMPLE_RATE)
    a2 = a2.filter('atrim', duration=song2_trim).filter('asetpts', 'PTS-STARTPTS')
    a2 = normalize_stream(a2, s2_lufs, target_lufs=TARGET_LUFS)
    # NO fade-out at end - next segment will handle the transition from this song

    # Apply transition
    # Song B needs to be delayed to start at segment_transition_pos, with a small head start
    delay_seconds = max(segment_transition_pos - (song_to_song_overlap / 2), 0)
    delay_ms = int(delay_seconds * 1000)
    logger.info(
        "Transition timing: segment_pos=%.2fs, crossfade=%.2fs, song2_delay=%dms (overlap padding %.2fs)",
        segment_transition_pos,
        crossfade_duration,
        delay_ms,
        song_to_song_overlap,
    )

    handoff_gap = song2_handoff_start - song2_trim
    if handoff_gap > 0:
        logger.warning(
            "Song B coverage ends %.2fs before the next segment's start (%.2fs). This would create a gap.",
            handoff_gap,
            song2_handoff_start,
        )
    
    # TTS timing (relative to segment start)
    actual_tts_start = segment_transition_pos - tts_offset_before_transition
    if actual_tts_start < 0:
        actual_tts_start = 0
    
    expected_duration = max(song1_segment_duration, delay_seconds + song2_trim)
    logger.info(
        "Expected segment duration: ~%.1fs (%.1f min) covering Song B to %.2fs",
        expected_duration,
        expected_duration / 60,
        song2_trim,
    )

    if transition_type == 'blend' or transition_type == 'crossfade':
        a2_delayed = a2.filter('adelay', f"{delay_ms}|{delay_ms}")
        mixed_music = transitions.apply_crossfade(a1, a2_delayed, crossfade_duration)
    elif transition_type == 'bass_swap':
        a2_delayed = a2.filter('adelay', f"{delay_ms}|{delay_ms}")
        swap_time = segment_transition_pos + (crossfade_duration / 2)
        mixed_music = transitions.apply_bass_swap(a1, a2_delayed, crossfade_duration, swap_time)
    elif transition_type == 'filter_sweep':
        a2_delayed = a2.filter('adelay', f"{delay_ms}|{delay_ms}")
        mixed_music = transitions.apply_filter_sweep(a1, a2_delayed, crossfade_duration)
    elif transition_type == 'echo_out':
        a2_delayed = a2.filter('adelay', f"{delay_ms}|{delay_ms}")
        mixed_music = transitions.apply_echo_out(a1, a2_delayed, crossfade_duration)
    elif transition_type == 'vinyl_stop':
        a2_delayed = a2.filter('adelay', f"{delay_ms}|{delay_ms}")
        mixed_music = transitions.apply_vinyl_stop(a1, a2_delayed, 2.0)
    else:
        a2_delayed = a2.filter('adelay', f"{delay_ms}|{delay_ms}")
        mixed_music = transitions.apply_crossfade(a1, a2_delayed, crossfade_duration)

    segment_metadata: Dict[str, Any] = {
        "song1": {
            "start": song1_start,
            "end": song1_start + song1_segment_duration,
            "transition_start": transition_start,
            "segment_transition_pos": segment_transition_pos,
        },
        "song2": {
            "start": 0.0,
            "end": song2_trim,
            "handoff_start": song2_handoff_start,
            "overlap_with_next": song_to_song_overlap,
        },
        "transition": {
            "type": transition_type,
            "crossfade_duration": crossfade_duration,
            "delay_ms": delay_ms,
            "start_in_segment": delay_seconds,
        },
        "render": {
            "expected_duration": expected_duration,
        }
    }

    # Handle TTS with ducking
    if tts_path and os.path.exists(tts_path):
        tts_in = ffmpeg.input(tts_path).audio
        tts = normalize_stream(tts_in.filter('aresample', SAMPLE_RATE), tts_lufs, target_lufs=TARGET_LUFS)

        actual_tts_end = actual_tts_start + tts_duration
        delay_ms_tts = int(actual_tts_start * 1000)
        tts_delayed = tts.filter('adelay', f"{delay_ms_tts}|{delay_ms_tts}")

        segment_metadata["tts"] = {
            "start": actual_tts_start,
            "end": actual_tts_end,
            "delay_ms": delay_ms_tts,
        }

        # Manual ducking for music
        ducked_music = mixed_music.filter(
            'volume', 
            enable=f'between(t,{actual_tts_start},{actual_tts_end})', 
            volume=TTS_DUCK_VOLUME
        )

        final_audio = (
            ffmpeg
            .filter([ducked_music, tts_delayed], 'amix', inputs=2, duration='longest', normalize=0)
            .filter('alimiter', limit=0.95)
        )
    else:
        final_audio = mixed_music.filter('alimiter', limit=0.95)

    # Render output
    try:
        logger.info(f"Generating transition segment: {output_path}...")
        output_node = ffmpeg.output(final_audio, output_path, acodec='libmp3lame', audio_bitrate='320k')
        (
            output_node
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )

        # Log actual output duration
        output_duration = get_duration(output_path)
        render_shortfall = expected_duration - output_duration
        if render_shortfall > 0.25:
            logger.warning(
                "Rendered segment is shorter than expected by %.2fs (expected %.2fs, actual %.2fs)",
                render_shortfall,
                expected_duration,
                output_duration,
            )

        segment_metadata["render"]["actual_duration"] = output_duration
        segment_metadata["render"]["handoff_gap"] = max(handoff_gap, 0)

        metadata_path = f"{output_path}.json"
        with open(metadata_path, "w", encoding="utf-8") as meta_file:
            json.dump(segment_metadata, meta_file, indent=2)

        logger.info(f"Success! Segment saved: {output_path} ({output_duration:.1f}s)")
        logger.info(f"Segment metadata saved: {metadata_path}")
        return {
            "output_path": output_path,
            "metadata_path": metadata_path,
            "metadata": segment_metadata,
        }
    except ffmpeg.Error as e:
        logger.error("Error occurred in FFmpeg:")
        logger.error(e.stderr.decode() if e.stderr else str(e))
        return None


def test_all_transitions(song1_path: str, song2_path: str):
    """
    Test all transition types with short snippets.
    
    Args:
        song1_path: Path to outgoing song
        song2_path: Path to incoming song
    """
    types = ['blend', 'bass_swap', 'filter_sweep', 'echo_out', 'vinyl_stop']
    for t in types:
        output = os.path.join(SEGMENT_DIR, f"test_{t}.mp3")
        create_dj_mix(
            song1_path=song1_path,
            song2_path=song2_path,
            transition_type=t,
            output_path=output,
            fast_test=True
        )


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python dj_mix.py <song1_path> <song2_path> [transition_type]")
        print("       python dj_mix.py --test-all <song1_path> <song2_path>")
        sys.exit(1)
    
    if sys.argv[1] == "--test-all":
        test_all_transitions(sys.argv[2], sys.argv[3])
    else:
        song1 = sys.argv[1]
        song2 = sys.argv[2]
        trans_type = sys.argv[3] if len(sys.argv) > 3 else 'blend'
        create_dj_mix(song1, song2, trans_type)
