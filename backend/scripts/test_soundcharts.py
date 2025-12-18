"""Test Soundcharts API connection and credentials."""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.integrations.soundcharts import get_soundcharts_client
import logging

logging.basicConfig(level=logging.DEBUG)

async def test_soundcharts():
    """Test Soundcharts API with a simple search."""
    print("=" * 60)
    print("Testing Soundcharts API Connection")
    print("=" * 60)
    
    client = get_soundcharts_client()
    
    if not client.enabled:
        print("[ERROR] Soundcharts client is disabled (missing credentials)")
        return False
    
    print(f"\n[OK] App ID: {client.app_id[:8]}...")
    print(f"[OK] API Key: {client.api_key[:8]}...")
    
    # Test search
    print("\n[TEST] Searching for 'Taylor Swift'...")
    
    try:
        results = await client.search_song("Taylor Swift", limit=3)
        
        if results:
            print(f"\n[SUCCESS] Found {len(results)} songs:")
            for i, song in enumerate(results, 1):
                print(f"  {i}. {song['title']} by {song['artist']}")
                print(f"     UUID: {song['uuid']}")
            return True
        else:
            print("\n[WARNING] No results returned (but no error)")
            print("This could mean:")
            print("  - Invalid credentials")
            print("  - No API access/subscription")
            print("  - Network/firewall issue")
            return False
    
    except Exception as e:
        print(f"\n[ERROR] {e}")
        return False

if __name__ == '__main__':
    success = asyncio.run(test_soundcharts())
    
    print("\n" + "=" * 60)
    if success:
        print("[SUCCESS] Soundcharts API is working correctly!")
    else:
        print("[FAILED] Soundcharts API test failed")
        print("\nTroubleshooting:")
        print("  1. Verify your credentials at https://soundcharts.com/")
        print("  2. Check if your API subscription is active")
        print("  3. Ensure your IP is not blocked")
        print("  4. Try the request in Postman/curl to isolate the issue")
    print("=" * 60)
    
    sys.exit(0 if success else 1)

