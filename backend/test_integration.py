"""Integration tests for AI DJ system."""
import pytest
import asyncio
from backend.db import Database
from backend.integrations.soundcharts import SoundchartsClient
from backend.integrations.openrouter import OpenRouterClient
from backend.integrations.elevenlabs import ElevenLabsClient
from backend.cache_manager import CacheManager


@pytest.mark.asyncio
async def test_database_connection():
    """Test database connection and basic operations."""
    db = Database(db_path=":memory:")
    await db.connect()
    
    # Test session creation
    await db.create_session("test-session-1", mode="autonomous")
    
    # Test song insertion
    song_data = {
        'uuid': 'test-uuid-123',
        'title': 'Test Song',
        'artist': 'Test Artist',
        'duration_sec': 180.0
    }
    await db.insert_song(song_data)
    
    # Retrieve song
    song = await db.get_song('test-uuid-123')
    assert song is not None
    assert song['title'] == 'Test Song'
    
    await db.close()


@pytest.mark.asyncio
async def test_cache_manager():
    """Test cache manager operations."""
    cache_mgr = CacheManager()
    
    # Get cache stats
    stats = await cache_mgr.get_cache_stats()
    assert 'used_bytes' in stats
    assert 'limit_bytes' in stats
    assert 'usage_percent' in stats


def test_soundcharts_client_init():
    """Test Soundcharts client initialization."""
    client = SoundchartsClient()
    assert client.base_url is not None
    assert client.headers is not None


def test_openrouter_client_init():
    """Test OpenRouter client initialization."""
    client = OpenRouterClient()
    assert client.model == "google/gemini-2.5-flash"
    assert client.base_url == "https://openrouter.ai/api/v1"


def test_elevenlabs_client_init():
    """Test ElevenLabs client initialization."""
    client = ElevenLabsClient()
    assert client.voice_id is not None
    assert client.model_id is not None


@pytest.mark.asyncio
async def test_segment_storage():
    """Test segment storage in database."""
    db = Database(db_path=":memory:")
    await db.connect()
    
    # Create session first
    await db.create_session("test-session-2", mode="autonomous")
    
    # Insert segment
    segment_data = {
        'session_id': 'test-session-2',
        'segment_index': 0,
        'song_uuid': 'test-song-uuid',
        'file_path_transport': '/tmp/segment_0.wav',
        'duration_sec': 30.0,
        'tts_used': 0
    }
    
    segment_id = await db.insert_segment(segment_data)
    assert segment_id > 0
    
    await db.close()


@pytest.mark.asyncio
async def test_play_history():
    """Test play history tracking."""
    db = Database(db_path=":memory:")
    await db.connect()
    
    # Create session
    await db.create_session("test-session-3", mode="autonomous")
    
    # Insert play history
    history_data = {
        'session_id': 'test-session-3',
        'song_uuid': 'test-song-1',
        'started_at': '2024-01-01T00:00:00',
        'skipped': 0,
        'transition_type': 'crossfade'
    }
    
    await db.insert_play_history(history_data)
    
    # Retrieve history
    history = await db.get_recent_plays('test-session-3', limit=5)
    assert len(history) == 1
    assert history[0]['song_uuid'] == 'test-song-1'
    
    await db.close()


def test_transitions_module():
    """Test new ffmpeg-python transitions module."""
    from backend.transitions import (
        apply_crossfade,
        apply_bass_swap,
        apply_filter_sweep,
        apply_echo_out,
        apply_vinyl_stop,
        get_transition_function,
        TRANSITION_FUNCTIONS
    )
    
    # Test transition registry
    assert 'blend' in TRANSITION_FUNCTIONS
    assert 'bass_swap' in TRANSITION_FUNCTIONS
    assert 'filter_sweep' in TRANSITION_FUNCTIONS
    assert 'echo_out' in TRANSITION_FUNCTIONS
    assert 'vinyl_stop' in TRANSITION_FUNCTIONS
    
    # Test get_transition_function
    blend_func = get_transition_function('blend')
    assert blend_func == apply_crossfade
    
    bass_func = get_transition_function('bass_swap')
    assert bass_func == apply_bass_swap
    
    # Test fallback for unknown type
    unknown_func = get_transition_function('unknown_type')
    assert unknown_func == apply_crossfade  # Should fallback to crossfade


def test_dj_mix_module():
    """Test DJ mix module functions."""
    from backend.dj_mix import (
        TARGET_LUFS,
        SAMPLE_RATE,
        TTS_DUCK_VOLUME,
        get_duration,
        get_loudness,
        create_dj_mix
    )
    
    # Test constants
    assert TARGET_LUFS == -14.0
    assert SAMPLE_RATE == 44100
    assert TTS_DUCK_VOLUME == 0.45
    
    # Test that functions exist
    assert callable(get_duration)
    assert callable(get_loudness)
    assert callable(create_dj_mix)


def test_ai_analyzer_module():
    """Test AI analyzer module functions."""
    from backend.ai_analyzer import (
        get_audio_format,
        _get_default_plan,
        _get_minimal_guide
    )
    
    # Test audio format detection
    assert get_audio_format("song.mp3") == "mp3"
    assert get_audio_format("song.mp4") == "mp4"
    assert get_audio_format("song.m4a") == "mp4"
    assert get_audio_format("song.wav") == "wav"
    assert get_audio_format("song.unknown") == "mp3"  # Default
    
    # Test default plan
    default_plan = _get_default_plan()
    assert default_plan["transition_type"] == "blend"
    assert default_plan["transition_start"] == 190.0
    assert default_plan["crossfade_duration"] == 10.0
    assert default_plan["tts_start_offset"] == 5.0
    
    # Test minimal guide
    guide = _get_minimal_guide()
    assert "blend" in guide.lower()
    assert "bass_swap" in guide.lower()
    assert "echo_out" in guide.lower()


def test_transition_plan_structure():
    """Test that transition plans have the expected structure."""
    from backend.ai_analyzer import _get_default_plan
    
    plan = _get_default_plan()
    
    # Required fields
    required_fields = [
        'transition_type',
        'transition_start',
        'crossfade_duration',
        'tts_start_offset',
        'analysis'
    ]
    
    for field in required_fields:
        assert field in plan, f"Missing required field: {field}"
    
    # Valid transition types
    valid_types = ['blend', 'bass_swap', 'filter_sweep', 'echo_out', 'vinyl_stop']
    assert plan['transition_type'] in valid_types


def test_config_transitions():
    """Test transition-related configuration."""
    from backend.config import (
        TARGET_LUFS,
        BASS_CROSSOVER_FREQ,
        TTS_DUCK_VOLUME,
        TRANSITION_GUIDE_PATH
    )
    
    assert TARGET_LUFS == -14.0
    assert BASS_CROSSOVER_FREQ == 250
    assert TTS_DUCK_VOLUME == 0.45
    assert TRANSITION_GUIDE_PATH is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

