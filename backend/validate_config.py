"""Validate configuration and API credentials on startup."""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

def validate_config():
    """Check if all required environment variables are set."""
    errors = []
    warnings = []
    
    # Required for core functionality
    required = {
        'OPENROUTER_API_KEY': 'OpenRouter API key for Gemini 2.5 Flash LLM',
        'SOUNDCHARTS_APP_ID': 'Soundcharts application ID',
        'SOUNDCHARTS_API_KEY': 'Soundcharts API key for song metadata',
        'ELEVENLABS_API_KEY': 'ElevenLabs API key for TTS'
    }
    
    # Optional with defaults
    optional = {
        'DB_PATH': 'data/persistence.db',
        'SONG_CACHE_DIR': 'data/cache/songs',
        'SEGMENT_DIR': 'data/segments',
        'TTS_DIR': 'data/tts',
        'CACHE_MAX_BYTES': '50000000000',
        'BACKEND_PORT': '8000',
        'ELEVENLABS_VOICE_ID': 'st7NwhTPEzqo2riw7qWC',
        'ELEVENLABS_MODEL_ID': 'eleven_flash_v2_5'
    }
    
    print("=" * 60)
    print("AI DJ Configuration Validation")
    print("=" * 60)
    
    # Check required variables
    print("\n✓ Required Configuration:")
    for var, description in required.items():
        value = os.getenv(var)
        if not value:
            errors.append(f"  ✗ {var}: NOT SET - {description}")
            print(f"  ✗ {var}: NOT SET")
        else:
            # Mask the actual value for security
            masked = value[:8] + "..." if len(value) > 8 else "***"
            print(f"  ✓ {var}: {masked}")
    
    # Check optional variables
    print("\n✓ Optional Configuration (with defaults):")
    for var, default in optional.items():
        value = os.getenv(var)
        if not value:
            print(f"  ○ {var}: using default '{default}'")
        else:
            print(f"  ✓ {var}: {value}")
    
    # Print results
    print("\n" + "=" * 60)
    if errors:
        print("❌ CONFIGURATION ERRORS:")
        for error in errors:
            print(error)
        print("\n💡 To fix:")
        print("  1. Copy .env.example to .env")
        print("  2. Add your API keys to .env")
        print("  3. Restart the server")
        print("=" * 60)
        return False
    else:
        print("✅ All required configuration is set!")
        print("=" * 60)
        return True

if __name__ == '__main__':
    if not validate_config():
        sys.exit(1)
    else:
        print("\n🚀 Ready to start AI DJ server!")

