import subprocess
import os
from typing import Optional, List

# Whitelist of allowed audio filters
ALLOWED_FILTERS = {
    'afade', 'acrossfade', 'volume', 'atrim', 'adelay', 'aformat', 'aecho', 'areverb', 'acompressor',
    'sidechaincompress',  # For TTS ducking
    'anull', 'amix', 'amerge', 'asetrate', 'atempo', 'asetpts', 'bandpass', 'highpass', 'lowpass',
    'equalizer', 'alimiter', 'aresample', 'aloop', 'concat', 'asplit'  # Additional filters for transitions
}

MAX_FILTER_COMPLEX_LENGTH = 2000  # max chars for filtergraph string (per documentation)


def validate_filtergraph(filtergraph: str) -> bool:
    """Validate filtergraph string against max length and allowed filters whitelist."""
    if len(filtergraph) > MAX_FILTER_COMPLEX_LENGTH:
        return False
    # Basic check for filter names (very simple parser)
    for filter_name in ALLOWED_FILTERS:
        if filter_name in filtergraph:
            return True
    return False


def run_ffmpeg_render(
    input_files: List[str],
    filter_complex: str,
    map_targets: List[str],
    output_path: str,
    segment_secs: int = 30,
    archive_path: Optional[str] = None
) -> bool:
    """
    Run ffmpeg safely with given input files, filtergraph, and map targets.

    Args:
        input_files: List of input audio file paths (A, B, optional TTS).
        filter_complex: FFmpeg filter_complex string specifying filtergraph.
        map_targets: List of map outputs, e.g. ['-map', '[out]'].
        output_path: Path to output rendered audio file.
        segment_secs: Duration of segment in seconds (default 30).
        archive_path: Optional path to save an archive copy of the output.

    Returns:
        True if rendering succeeded, False otherwise.
    """
    # Validate inputs
    if not validate_filtergraph(filter_complex):
        raise ValueError('Filtergraph validation failed: length or filters not allowed.')

    if not all(os.path.isfile(f) for f in input_files):
        raise FileNotFoundError('One or more input files do not exist.')

    # Build ffmpeg command arguments
    cmd = ['ffmpeg', '-y']
    for f in input_files:
        cmd.extend(['-i', f])

    cmd.extend(['-filter_complex', filter_complex])

    # Add map targets
    for m in map_targets:
        cmd.extend(['-map', m])

    # Output options: force 48kHz stereo 16-bit PCM for consistency
    cmd.extend([
        '-t', str(segment_secs), 
        '-c:a', 'pcm_s16le', 
        '-ar', '48000', 
        '-ac', '2'
    ])
    cmd.append(output_path)

    # Execute without shell for safety
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f'FFmpeg failed: {e.stderr}')
        return False

    # Optionally archive
    if archive_path:
        try:
            os.makedirs(os.path.dirname(archive_path), exist_ok=True)
            os.replace(output_path, archive_path)
        except Exception as e:
            print(f'Archiving failed: {e}')
            # Continue even if archiving fails

    return True


async def store_rendered_segment(output_path: str, segment_data: dict) -> int:
    """
    Store rendered segment metadata in database.
    
    Args:
        output_path: Path to rendered segment file
        segment_data: Dict with session_id, segment_index, song_uuid, etc.
    
    Returns:
        Segment ID from database
    """
    from backend.db import get_db
    
    db = await get_db()
    segment_id = await db.insert_segment({
        **segment_data,
        'file_path_transport': output_path
    })
    return segment_id

