import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env

# Configuration placeholders
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
SOUNDCHARTS_APP_ID = os.getenv('SOUNDCHARTS_APP_ID')
SOUNDCHARTS_API_KEY = os.getenv('SOUNDCHARTS_API_KEY')
SOUNDCHARTS_BASE_URL = os.getenv('SOUNDCHARTS_BASE_URL', 'https://api.soundcharts.com/api/v2')
ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY')
ELEVENLABS_VOICE_ID = os.getenv('ELEVENLABS_VOICE_ID', 'st7NwhTPEzqo2riw7qWC')
ELEVENLABS_MODEL_ID = os.getenv('ELEVENLABS_MODEL_ID', 'eleven_flash_v2_5')
DB_PATH = os.getenv('DB_PATH', 'data/persistence.db')
CACHE_MAX_BYTES = 50_000_000_000
SONG_CACHE_DIR = os.getenv('SONG_CACHE_DIR', 'data/cache/songs')
SEGMENT_DIR = os.getenv('SEGMENT_DIR', 'data/segments')
TTS_DIR = os.getenv('TTS_DIR', 'data/tts')

# User personalization
USER_CONTEXT_FILE = os.getenv('USER_CONTEXT_FILE', 'data/user_context.txt')

# Agent thinking budgets (per DOCUMENTATION.md)
THINKING_BUDGETS = {
    'track_selector': int(os.getenv('THINKING_BUDGET_TRACK', '2000')),  # Medium
    'transition_planner': int(os.getenv('THINKING_BUDGET_TRANSITION', '1500')),  # Low-medium (deterministic)
    'speech_writer': int(os.getenv('THINKING_BUDGET_SPEECH', '3500')),  # Medium-high (creative)
}

# Transition settings
TRANSITION_TYPES_ENABLED = os.getenv('TRANSITION_TYPES', 'all').split(',')
TRANSITION_GUIDE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'docs', 'transition-field-guide.md')

# Audio processing constants (from v2.0 DJ mix engine)
TARGET_LUFS = float(os.getenv('TARGET_LUFS', '-14.0'))  # Global streaming standard
BASS_CROSSOVER_FREQ = float(os.getenv('BASS_CROSSOVER_FREQ', '250'))  # Hz for bass swap
TTS_DUCK_VOLUME = float(os.getenv('TTS_DUCK_VOLUME', '0.45'))  # ~-7dB during talkover