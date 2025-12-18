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
TTS_DUCK_VOLUME = 0.8  # Even louder music during DJ talk


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
) -> Optional[str]:
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
        Path to the rendered output file, or None on error
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
    transition_start = t_start if t_start is not None else (song1_duration - crossfade_duration - 20)
    
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
    
    # How much of song A to include BEFORE transition
    # Keep this minimal to avoid repeating what was already played in intro/previous segment
    # The previous segment already played song A up to ~(duration-30), so we only need
    # a brief lead-in for the crossfade to sound natural
    song1_lead_in = 20.0  # 20 seconds lead-in to match transition_buffer in graph.py
    
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
    
    # Rough estimate of next transition start relative to song B start:
    song2_next_transition_start = song2_duration - 20
    
    # Calculate trim point:
    # We want to keep audio until: next_transition_start - lead_in
    # This ensures next segment picks up exactly there
    song2_trim = song2_next_transition_start - song1_lead_in
    
    if song2_trim < 60:
        song2_trim = song2_duration  # Use full song if very short
    
    logger.info(f"--- [TRANSITION SEGMENT] Mode: {transition_type} ---")
    logger.info(f"Song A: {song1_segment_duration:.1f}s included (from {song1_start:.1f}s, transition at {transition_start:.1f}s)")
    logger.info(f"Song B: {song2_trim:.1f}s included (of {song2_duration:.1f}s total)")
    expected_duration = segment_transition_pos + crossfade_duration + song2_trim
    logger.info(f"Expected segment duration: ~{expected_duration:.1f}s ({expected_duration/60:.1f} min)")
    
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
    # Song B needs to be delayed to start at segment_transition_pos
    delay_ms = int(segment_transition_pos * 1000)
    logger.info(f"Transition timing: segment_pos={segment_transition_pos}s, crossfade={crossfade_duration}s, song2_delay={delay_ms}ms")
    
    # TTS timing (relative to segment start)
    actual_tts_start = segment_transition_pos - tts_offset_before_transition
    if actual_tts_start < 0:
        actual_tts_start = 0
    
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

    # Handle TTS with ducking
    if tts_path and os.path.exists(tts_path):
        tts_in = ffmpeg.input(tts_path).audio
        tts = normalize_stream(tts_in.filter('aresample', SAMPLE_RATE), tts_lufs, target_lufs=TARGET_LUFS)
        
        actual_tts_end = actual_tts_start + tts_duration
        delay_ms_tts = int(actual_tts_start * 1000)
        tts_delayed = tts.filter('adelay', f"{delay_ms_tts}|{delay_ms_tts}")

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
        logger.info(f"Success! Segment saved: {output_path} ({output_duration:.1f}s)")
        return output_path
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
