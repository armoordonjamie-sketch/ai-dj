"""Inspect Soundcharts SDK to find available methods."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from soundcharts.client import SoundchartsClient
    from backend.config import SOUNDCHARTS_APP_ID, SOUNDCHARTS_API_KEY
    
    print("=" * 60)
    print("Soundcharts SDK Method Inspector")
    print("=" * 60)
    
    # Initialize client
    sc = SoundchartsClient(
        app_id=SOUNDCHARTS_APP_ID,
        api_key=SOUNDCHARTS_API_KEY
    )
    
    print("\nAvailable modules and methods:\n")
    
    # Inspect search module
    print("search module:")
    if hasattr(sc, 'search'):
        methods = [m for m in dir(sc.search) if not m.startswith('_')]
        for method in methods:
            print(f"  - search.{method}")
    
    # Inspect song module
    print("\nsong module:")
    if hasattr(sc, 'song'):
        methods = [m for m in dir(sc.song) if not m.startswith('_')]
        for method in methods:
            print(f"  - song.{method}")
    
    # Inspect artist module
    print("\nartist module:")
    if hasattr(sc, 'artist'):
        methods = [m for m in dir(sc.artist) if not m.startswith('_')]
        for method in methods:
            print(f"  - artist.{method}")
    
    # List all top-level attributes
    print("\nAll client attributes:")
    attrs = [a for a in dir(sc) if not a.startswith('_')]
    for attr in attrs:
        print(f"  - {attr}")
    
    print("\n" + "=" * 60)
    print("Use these method names in soundcharts.py")
    print("=" * 60)
    
except ImportError as e:
    print(f"Error: Soundcharts SDK not installed - {e}")
    print("Run: pip install soundcharts")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

