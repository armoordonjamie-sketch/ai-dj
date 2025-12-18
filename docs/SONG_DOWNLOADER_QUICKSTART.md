# Song Downloader Quick Start

## Overview

The AI DJ uses **yt-dlp** to download songs from YouTube and other platforms. Songs are automatically converted to MP3 format and stored in the cache with metadata in the database.

## Prerequisites

1. **FFmpeg** must be installed:
   - Windows: Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH
   - Mac: `brew install ffmpeg`
   - Linux: `sudo apt-get install ffmpeg`

2. **Python dependencies**:
   ```bash
   pip install yt-dlp
   ```

## Quick Start

### Download Songs Automatically

```bash
# Download a curated list of 8 popular songs
python backend/scripts/populate_song_cache.py
```

This downloads:
- Taylor Swift - Shake It Off
- Taylor Swift - Blank Space
- Taylor Swift - Style
- Taylor Swift - Bad Blood
- Mark Ronson - Uptown Funk
- Shania Twain - Man! I Feel Like A Woman!
- Dua Lipa - Levitating
- The Weeknd - Blinding Lights

### Download Individual Songs

```bash
# Basic usage (searches YouTube)
python backend/song_downloader.py "Taylor Swift Shake It Off"

# With metadata for better organization
python backend/song_downloader.py "shake it off" "Taylor Swift" "Shake It Off"
```

## Programmatic Usage

```python
import asyncio
from backend.song_downloader import SongDownloader

async def download_songs():
    downloader = SongDownloader()
    
    # Download single song
    result = await downloader.download_song(
        query="Dua Lipa Levitating",
        artist="Dua Lipa",
        title="Levitating"
    )
    
    if result:
        print(f"Downloaded: {result['file_path']}")
        print(f"Duration: {result['duration_sec']}s")
    
    # Download multiple songs
    songs = [
        {'query': 'The Weeknd Blinding Lights'},
        {'query': 'Billie Eilish Bad Guy'},
    ]
    
    results = await downloader.download_multiple(songs)
    print(f"Downloaded {sum(1 for r in results if r)} songs")

asyncio.run(download_songs())
```

## Cache Management

```python
from backend.song_downloader import SongDownloader

downloader = SongDownloader()

# List all cached songs
songs = downloader.get_cached_songs()
for song in songs:
    print(song.name)

# Get cache size
size_mb = downloader.get_cache_size() / (1024 * 1024)
print(f"Cache size: {size_mb:.2f} MB")
```

## How It Works

1. **Search**: Searches YouTube for the query (e.g., "Taylor Swift Shake It Off")
2. **Download**: Downloads the best audio quality available
3. **Convert**: Extracts audio and converts to MP3 (192kbps)
4. **Store**: Saves to `backend/song-cache/` with format: `Artist - Title.mp3`
5. **Database**: Stores metadata (title, artist, duration, file path) in SQLite

## File Locations

- **Cache Directory**: `backend/song-cache/`
- **Database**: `data/persistence.db`
- **Downloaded Format**: MP3 at 192kbps (~3-5 MB per song)

## Troubleshooting

### FFmpeg Not Found

```
ERROR: ffmpeg not found
```

**Solution**: Install FFmpeg and ensure it's in your PATH. Test with:
```bash
ffmpeg -version
```

### Download Fails

```
ERROR: Unable to download video
```

**Possible causes**:
- Video is private/deleted
- Network issues
- YouTube rate limiting

**Solution**: Try a different search query or wait a few minutes

### Permission Errors

```
ERROR: Permission denied
```

**Solution**: Ensure cache directory is writable:
```bash
chmod 755 backend/song-cache
```

## Advanced Usage

### Custom Cache Directory

```python
downloader = SongDownloader(cache_dir="/path/to/custom/cache")
```

### Batch Download with Custom List

```python
songs = [
    {'query': 'Artist1 Song1', 'artist': 'Artist1', 'title': 'Song1'},
    {'query': 'Artist2 Song2', 'artist': 'Artist2', 'title': 'Song2'},
]

results = await downloader.download_multiple(songs)
```

## Integration with AI DJ

The song downloader integrates seamlessly with the AI DJ system:

1. **Soundcharts** finds song metadata
2. **Song Downloader** downloads the audio file
3. **Database** stores both metadata and file path
4. **DJ Loop** uses cached songs for playback

## Performance

- **Download Speed**: 10-30 seconds per song (depends on connection)
- **File Size**: ~3-5 MB per song (192kbps MP3)
- **Cache Capacity**: 50GB = ~10,000-15,000 songs
- **Rate Limiting**: 2-second delay between downloads to avoid throttling

## References

- [yt-dlp GitHub](https://github.com/yt-dlp/yt-dlp) - Official documentation
- [FFmpeg](https://ffmpeg.org/) - Audio processing tool
- [Song Downloader Implementation Notes](./song-downloader-notes.md) - Detailed technical docs

