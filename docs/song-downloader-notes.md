# Song Downloader - Implementation Notes

## What Was Implemented

### Files Created
- **`backend/song_downloader.py`**: Main song downloader module using yt-dlp
- **`backend/scripts/populate_song_cache.py`**: Script to populate cache with initial songs

### Key Components

#### SongDownloader Class
- Downloads songs from YouTube using yt-dlp
- Extracts audio as MP3 (192kbps quality)
- Stores metadata in SQLite database
- Manages song cache directory
- Supports batch downloads with rate limiting

## How to Run Locally

### Prerequisites

1. **Install yt-dlp and FFmpeg**:
   ```bash
   # Install Python dependencies
   pip install -r requirements.txt
   
   # FFmpeg is required for audio extraction
   # Windows: Download from https://ffmpeg.org/download.html
   # Mac: brew install ffmpeg
   # Linux: sudo apt-get install ffmpeg
   ```

2. **Verify FFmpeg installation**:
   ```bash
   ffmpeg -version
   ```

### Download Individual Songs

```bash
# Basic usage
python backend/song_downloader.py "Taylor Swift Shake It Off"

# With artist and title metadata
python backend/song_downloader.py "shake it off" "Taylor Swift" "Shake It Off"
```

### Populate Song Cache

```bash
# Download a curated list of songs
python backend/scripts/populate_song_cache.py
```

This will download:
- Taylor Swift - Shake It Off
- Taylor Swift - Blank Space
- Taylor Swift - Style
- Taylor Swift - Bad Blood
- Mark Ronson - Uptown Funk
- Shania Twain - Man! I Feel Like A Woman!
- Dua Lipa - Levitating
- The Weeknd - Blinding Lights

### Check Cache Status

```python
from backend.song_downloader import SongDownloader

downloader = SongDownloader()

# List all cached songs
songs = downloader.get_cached_songs()
for song in songs:
    print(song.name)

# Get cache size
size_bytes = downloader.get_cache_size()
size_mb = size_bytes / (1024 * 1024)
print(f"Cache size: {size_mb:.2f} MB")
```

## Interfaces & Contracts

### SongDownloader API

```python
class SongDownloader:
    def __init__(self, cache_dir: str = SONG_CACHE_DIR):
        """Initialize with cache directory."""
    
    async def download_song(
        self, 
        query: str, 
        artist: Optional[str] = None,
        title: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Download a song from YouTube.
        
        Args:
            query: Search query (e.g., "Taylor Swift Shake It Off")
            artist: Optional artist name for metadata
            title: Optional song title for metadata
        
        Returns:
            {
                'file_path': str,
                'title': str,
                'artist': str,
                'duration_sec': int,
                'youtube_id': str,
                'youtube_url': str,
                'thumbnail_url': str
            }
        """
    
    async def download_multiple(
        self, 
        songs: List[Dict[str, str]]
    ) -> List[Optional[Dict[str, Any]]]:
        """Download multiple songs with rate limiting."""
    
    def get_cached_songs(self) -> List[Path]:
        """Get list of all cached MP3 files."""
    
    def get_cache_size(self) -> int:
        """Get total cache size in bytes."""
```

### Database Schema

Songs are stored in the `songs` table with:
- `uuid`: Unique identifier
- `title`: Song title
- `artist`: Artist name
- `duration_sec`: Duration in seconds
- `file_path`: Path to MP3 file
- `youtube_id`: YouTube video ID
- `youtube_url`: YouTube URL

## Architecture Decisions

### Why yt-dlp?

1. **Feature-rich**: Supports 1000+ sites, not just YouTube
2. **Active development**: Fork of youtube-dl with better maintenance
3. **Python API**: Easy integration with async code
4. **Audio extraction**: Built-in FFmpeg integration for MP3 conversion
5. **Metadata extraction**: Rich metadata including duration, artist, etc.

**Reference**: [yt-dlp GitHub](https://github.com/yt-dlp/yt-dlp)

### Audio Format Choice

- **Format**: MP3 at 192kbps
- **Rationale**: 
  - Good balance between quality and file size
  - Universal compatibility
  - ~3-5 MB per song (3-4 minute songs)
  - 50GB cache = ~10,000-15,000 songs

### Async Integration

- Uses `asyncio.to_thread()` to run synchronous yt-dlp in thread pool
- Prevents blocking the event loop during downloads
- Allows concurrent downloads with rate limiting

### Database Integration

- Automatically stores downloaded songs in SQLite
- Tracks file paths for quick lookup
- Stores YouTube metadata for reference
- Enables cache management and eviction

## TODOs & Known Limitations

### Current Limitations

1. **No YouTube Music API**: Uses search, may not always find exact match
2. **No Spotify Integration**: Can't download directly from Spotify
3. **No Audio Fingerprinting**: Can't verify if downloaded song matches request
4. **Basic Error Handling**: Could be more robust for network failures
5. **No Resume Support**: Failed downloads must restart from beginning

### Future Improvements

1. **Spotify Integration**:
   - Use Spotify API to get exact song metadata
   - Search YouTube with artist + title for better accuracy
   - Match duration to verify correct song

2. **Audio Fingerprinting**:
   - Use AcoustID or similar to verify downloaded audio
   - Ensure downloaded song matches requested song

3. **Download Queue**:
   - Background download queue
   - Retry failed downloads
   - Resume interrupted downloads

4. **Cache Management**:
   - Integrate with `CacheManager` for automatic eviction
   - Track play counts to keep popular songs
   - Automatic cleanup of old/unused songs

5. **Quality Options**:
   - Configurable bitrate (128kbps, 192kbps, 320kbps)
   - Option for lossless formats (FLAC)

6. **Metadata Enhancement**:
   - Fetch album art from Spotify/Last.fm
   - Embed ID3 tags in MP3 files
   - Store genre, release year, etc.

## Dependencies Added

### yt-dlp (2024.12.13)
- **Purpose**: Download audio from YouTube and 1000+ sites
- **Why**: Most reliable and feature-rich video/audio downloader
- **License**: Unlicense (public domain)
- **Requires**: FFmpeg for audio extraction

### FFmpeg (External Dependency)
- **Purpose**: Audio extraction and conversion to MP3
- **Installation**: Must be installed separately and in PATH
- **Why**: Industry standard for audio/video processing
- **License**: LGPL/GPL

## Usage Examples

### Programmatic Usage

```python
import asyncio
from backend.song_downloader import SongDownloader

async def main():
    downloader = SongDownloader()
    
    # Download single song
    result = await downloader.download_song(
        query="Taylor Swift Shake It Off",
        artist="Taylor Swift",
        title="Shake It Off"
    )
    
    if result:
        print(f"Downloaded: {result['file_path']}")
    
    # Download multiple songs
    songs = [
        {'query': 'Dua Lipa Levitating', 'artist': 'Dua Lipa', 'title': 'Levitating'},
        {'query': 'The Weeknd Blinding Lights', 'artist': 'The Weeknd', 'title': 'Blinding Lights'},
    ]
    
    results = await downloader.download_multiple(songs)
    print(f"Downloaded {sum(1 for r in results if r)} songs")

asyncio.run(main())
```

### Integration with DJ Loop

The song downloader can be integrated into the DJ loop to automatically download songs that aren't in the cache:

```python
# In TrackSelectorAgent
async def select_track(state):
    # Search Soundcharts for song
    songs = await soundcharts.search_song(query)
    
    # Check if song is in cache
    song_uuid = songs[0]['uuid']
    cached_song = await db.get_song_by_uuid(song_uuid)
    
    if not cached_song or not os.path.exists(cached_song['file_path']):
        # Download song
        downloader = SongDownloader()
        result = await downloader.download_song(
            query=f"{songs[0]['artist']} {songs[0]['title']}",
            artist=songs[0]['artist'],
            title=songs[0]['title']
        )
        
        if result:
            # Update database with file path
            await db.update_song_file_path(song_uuid, result['file_path'])
    
    return songs[0]
```

## Testing

### Manual Testing

```bash
# Test single download
python backend/song_downloader.py "test song"

# Test batch download
python backend/scripts/populate_song_cache.py

# Verify cache
ls -lh backend/song-cache/
```

### Automated Testing

```python
# tests/test_song_downloader.py
import pytest
from backend.song_downloader import SongDownloader

@pytest.mark.asyncio
async def test_download_song():
    downloader = SongDownloader()
    result = await downloader.download_song(
        query="test song",
        artist="Test Artist",
        title="Test Song"
    )
    
    assert result is not None
    assert result['file_path'].endswith('.mp3')
    assert os.path.exists(result['file_path'])
```

## Security Considerations

1. **Filename Sanitization**: All filenames are sanitized to prevent path traversal
2. **Cache Directory**: Restricted to configured cache directory
3. **No User Input in Shell**: yt-dlp is called via Python API, not shell commands
4. **Rate Limiting**: Built-in delays to avoid overwhelming YouTube
5. **Error Handling**: Graceful handling of download failures

## Performance

- **Download Speed**: Depends on internet connection and YouTube throttling
- **Typical Download Time**: 10-30 seconds per song
- **Concurrent Downloads**: Supports batch downloads with rate limiting
- **Cache Lookup**: O(1) database lookup for cached songs
- **File Size**: ~3-5 MB per song (192kbps MP3)

## Troubleshooting

### FFmpeg Not Found

```
ERROR: ffmpeg not found. Please install ffmpeg
```

**Solution**: Install FFmpeg and ensure it's in your PATH

### Download Fails

```
ERROR: Unable to download video
```

**Possible causes**:
- Video is private/deleted
- Network connectivity issues
- YouTube rate limiting

**Solution**: Try again later or use a different search query

### Permission Errors

```
ERROR: Permission denied
```

**Solution**: Ensure cache directory is writable:
```bash
chmod 755 backend/song-cache
```

