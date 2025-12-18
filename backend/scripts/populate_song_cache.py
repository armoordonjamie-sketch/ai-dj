"""Script to populate the song cache with initial songs for testing."""
import sys
import asyncio
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.song_downloader import SongDownloader


async def populate_cache():
    """Download a set of popular songs to populate the cache."""
    
    downloader = SongDownloader()
    
    # List of songs to download
    songs_to_download = [
        {
            'query': 'Taylor Swift Shake It Off',
            'artist': 'Taylor Swift',
            'title': 'Shake It Off'
        },
        {
            'query': 'Taylor Swift Blank Space',
            'artist': 'Taylor Swift',
            'title': 'Blank Space'
        },
        {
            'query': 'Taylor Swift Style',
            'artist': 'Taylor Swift',
            'title': 'Style'
        },
        {
            'query': 'Taylor Swift Bad Blood',
            'artist': 'Taylor Swift',
            'title': 'Bad Blood'
        },
        {
            'query': 'Mark Ronson Uptown Funk',
            'artist': 'Mark Ronson ft. Bruno Mars',
            'title': 'Uptown Funk'
        },
        {
            'query': 'Shania Twain Man I Feel Like A Woman',
            'artist': 'Shania Twain',
            'title': 'Man! I Feel Like A Woman!'
        },
        {
            'query': 'Dua Lipa Levitating',
            'artist': 'Dua Lipa',
            'title': 'Levitating'
        },
        {
            'query': 'The Weeknd Blinding Lights',
            'artist': 'The Weeknd',
            'title': 'Blinding Lights'
        },
    ]
    
    print("=" * 60)
    print("AI DJ Song Cache Population")
    print("=" * 60)
    print(f"\nDownloading {len(songs_to_download)} songs...")
    print(f"Cache directory: {downloader.cache_dir}\n")
    
    # Check existing cache
    existing_songs = downloader.get_cached_songs()
    print(f"Existing songs in cache: {len(existing_songs)}")
    
    if existing_songs:
        print("\nExisting songs:")
        for song in existing_songs:
            print(f"  - {song.name}")
        print()
    
    # Download songs
    results = await downloader.download_multiple(songs_to_download)
    
    # Summary
    print("\n" + "=" * 60)
    print("Download Summary")
    print("=" * 60)
    
    successful = sum(1 for r in results if r is not None)
    failed = len(results) - successful
    
    print(f"\nSuccessful: {successful}/{len(results)}")
    print(f"Failed: {failed}/{len(results)}")
    
    # Show cache stats
    cache_size = downloader.get_cache_size()
    cache_size_mb = cache_size / (1024 * 1024)
    total_songs = len(downloader.get_cached_songs())
    
    print(f"\nCache Statistics:")
    print(f"  Total songs: {total_songs}")
    print(f"  Total size: {cache_size_mb:.2f} MB")
    
    print("\n" + "=" * 60)
    print("✓ Song cache population complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(populate_cache())

