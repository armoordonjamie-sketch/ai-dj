"""AI Audio Analyzer for transition planning.

This module uses Gemini via OpenRouter to analyze audio tracks
and determine optimal transition parameters (BPM, transition type,
timing, crossfade duration).

Adapted from v2.0 AI analyzer.
"""
import os
import base64
import json
import logging
from typing import Dict, Any, Optional

from openai import OpenAI
from backend.config import OPENROUTER_API_KEY

logger = logging.getLogger(__name__)

# Path to the transition field guide
TRANSITION_GUIDE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 
    "docs", 
    "transition-field-guide.md"
)


def encode_audio(file_path: str) -> str:
    """
    Encode an audio file to base64 for LLM input.
    
    Args:
        file_path: Path to the audio file
        
    Returns:
        Base64-encoded string of the audio data
    """
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode('utf-8')


def get_audio_format(file_path: str) -> str:
    """
    Determine audio format from file extension.
    
    Args:
        file_path: Path to the audio file
        
    Returns:
        Format string for the API (mp3, mp4, wav, etc.)
    """
    ext = os.path.splitext(file_path)[1].lower()
    format_map = {
        '.mp3': 'mp3',
        '.mp4': 'mp4',
        '.m4a': 'mp4',
        '.wav': 'wav',
        '.webm': 'webm',
        '.ogg': 'ogg',
        '.flac': 'flac',
    }
    return format_map.get(ext, 'mp3')


def analyze_tracks(
    song1_path: str, 
    song2_path: str, 
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Analyze two tracks using AI to determine optimal transition parameters.
    
    Sends both audio tracks to Gemini via OpenRouter for analysis.
    The model listens to the outro of Song 1 and intro of Song 2,
    then determines the best transition type and timing.
    
    Args:
        song1_path: Path to the outgoing (Song A) audio file
        song2_path: Path to the incoming (Song B) audio file
        api_key: OpenRouter API key (uses config if None)
        
    Returns:
        Dict with transition plan:
        {
            "transition_type": "bass_swap",
            "transition_start": 196.5,
            "crossfade_duration": 10.0,
            "tts_start_offset": 5.0,
            "analysis": "Explanation of why this transition was chosen"
        }
    """
    if api_key is None:
        api_key = OPENROUTER_API_KEY
        
    if not api_key:
        logger.error("OpenRouter API key not configured")
        return _get_default_plan()
    
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )
    
    # Read the transition guide for context
    guide_content = ""
    try:
        if os.path.exists(TRANSITION_GUIDE_PATH):
            with open(TRANSITION_GUIDE_PATH, "r", encoding="utf-8") as f:
                guide_content = f.read()
        else:
            logger.warning(f"Transition guide not found at {TRANSITION_GUIDE_PATH}")
            guide_content = _get_minimal_guide()
    except Exception as e:
        logger.error(f"Failed to read transition guide: {e}")
        guide_content = _get_minimal_guide()

    logger.info(f"Analyzing tracks: {song1_path} and {song2_path}...")
    
    # Encode both audio files
    try:
        s1_base64 = encode_audio(song1_path)
        s2_base64 = encode_audio(song2_path)
    except Exception as e:
        logger.error(f"Failed to encode audio files: {e}")
        return _get_default_plan()
    
    # Get audio formats
    s1_format = get_audio_format(song1_path)
    s2_format = get_audio_format(song2_path)
    
    prompt = f"""
    You are an expert AI DJ. You have been provided with two tracks and a transition field guide.
    
    ### Available Transitions:
    {guide_content}
    
    ### Your Task:
    1. Listen to the outro of Song 1 and the intro of Song 2.
    2. Determine the BPM and Energy of both.
    3. Choose the BEST transition type from the guide (blend, bass_swap, filter_sweep, echo_out, vinyl_stop).
    4. Provide the exact timing for the mix.
    
    ### Requirements:
    - Output ONLY a valid JSON object.
    - Song durations are roughly 210 seconds each.
    - 'transition_start' should be the timestamp in Song 1 where the transition begins (usually 10-20s before the end).
    - 'crossfade_duration' should be between 5 and 15 seconds.
    - 'tts_start_offset' is how many seconds BEFORE 'transition_start' the DJ should start talking.
    
    ### Output Format:
    {{
      "transition_type": "bass_swap",
      "transition_start": 196.5,
      "crossfade_duration": 10.0,
      "tts_start_offset": 5.0,
      "analysis": "Briefly explain why you chose this transition."
    }}
    """

    try:
        response = client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "input_audio",
                            "input_audio": {"data": s1_base64, "format": s1_format}
                        },
                        {
                            "type": "input_audio",
                            "input_audio": {"data": s2_base64, "format": s2_format}
                        }
                    ]
                }
            ],
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)
        logger.info(f"AI analysis complete: {result.get('transition_type')} - {result.get('analysis', '')[:100]}")
        return result
        
    except Exception as e:
        logger.error(f"AI analysis failed: {e}")
        return _get_default_plan()


async def analyze_tracks_async(
    song1_path: str, 
    song2_path: str, 
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Async version of analyze_tracks for use with LangGraph.
    
    Args:
        song1_path: Path to the outgoing (Song A) audio file
        song2_path: Path to the incoming (Song B) audio file
        api_key: OpenRouter API key (uses config if None)
        
    Returns:
        Dict with transition plan
    """
    import asyncio
    # Run sync function in executor to avoid blocking
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, 
        analyze_tracks, 
        song1_path, 
        song2_path, 
        api_key
    )


def _get_default_plan() -> Dict[str, Any]:
    """
    Get a safe default transition plan when AI analysis fails.
    
    Returns:
        Dict with default crossfade transition
    """
    return {
        "transition_type": "blend",
        "transition_start": 190.0,
        "crossfade_duration": 10.0,
        "tts_start_offset": 5.0,
        "analysis": "Default fallback - using safe crossfade transition"
    }


def _get_minimal_guide() -> str:
    """
    Get a minimal transition guide when the full guide is unavailable.
    
    Returns:
        String with basic transition descriptions
    """
    return """
    Available transition types:
    
    1. blend (crossfade): Standard linear crossfade. Best for similar tempo/energy tracks.
    
    2. bass_swap: Swap bass frequencies at the transition point while crossfading highs.
       Best for house/techno where you want to maintain groove.
    
    3. filter_sweep: LPF sweep on outgoing, HPF opening on incoming.
       Best for smoothing harmonic clashes.
    
    4. echo_out: Add feedback delay tail to outgoing track.
       Best for dramatic exits or when keys clash.
    
    5. vinyl_stop: Turntable brake effect on outgoing track.
       Best for dramatic genre/tempo changes.
    
    Choose based on:
    - Similar tempo (±5 BPM) → blend or bass_swap
    - Key clash → echo_out or filter_sweep  
    - Big tempo/energy change → vinyl_stop or echo_out
    - Maintaining groove → bass_swap
    """


if __name__ == "__main__":
    # Test the analyzer
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python ai_analyzer.py <song1_path> <song2_path>")
        sys.exit(1)
    
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("Error: OPENROUTER_API_KEY not found in environment.")
        sys.exit(1)
    
    song1 = sys.argv[1]
    song2 = sys.argv[2]
    plan = analyze_tracks(song1, song2, api_key)
    print("AI DJ Plan:")
    print(json.dumps(plan, indent=2))

