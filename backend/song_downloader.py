"""Song downloader using yt-dlp for AI DJ system.

Downloads songs from YouTube and other platforms, extracts audio as MP3,
and stores metadata in the database.
"""
import os
import sys
import logging
import asyncio
from typing import Optional, Dict, Any, List
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import yt_dlp
from backend.config import SONG_CACHE_DIR
from backend.db import get_db


class SongDownloader:
    """Downloads songs using yt-dlp and manages the song cache."""
    
    def __init__(self, cache_dir: str = SONG_CACHE_DIR):
        """
        Initialize the song downloader.
        
        Args:
            cache_dir: Directory to store downloaded songs
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Default yt-dlp options for audio extraction
        self.base_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': str(self.cache_dir / '%(artist)s - %(title)s.%(ext)s'),
            'quiet': False,
            'no_warnings': False,
            'extract_flat': False,
            'ignoreerrors': False,
        }
    
    async def download_song(
        self, 
        query: str, 
        artist: Optional[str] = None,
        title: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Download a song from YouTube by search query.
        
        Args:
            query: Search query (e.g., "Taylor Swift Shake It Off")
            artist: Optional artist name for metadata
            title: Optional song title for metadata
        
        Returns:
            Dict with song info and file path, or None if failed
        """
        try:
            # Build search URL
            search_url = f"ytsearch1:{query}"
            
            logging.info(f"Downloading song: {query}")
            
            # Run yt-dlp in thread pool to avoid blocking
            result = await asyncio.to_thread(
                self._download_with_ytdlp,
                search_url,
                artist,
                title
            )
            
            if result:
                # Store in database
                await self._store_in_db(result)
                logging.info(f"Successfully downloaded: {result['file_path']}")
            
            return result
        
        except Exception as e:
            logging.error(f"Error downloading song '{query}': {e}")
            return None
    
    def _download_with_ytdlp(
        self, 
        url: str,
        artist: Optional[str] = None,
        title: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Synchronous download using yt-dlp.
        
        Args:
            url: YouTube URL or search query
            artist: Optional artist name
            title: Optional song title
        
        Returns:
            Dict with download info or None
        """
        opts = self.base_opts.copy()
        
        # Custom output template if artist/title provided
        if artist and title:
            safe_artist = self._sanitize_filename(artist)
            safe_title = self._sanitize_filename(title)
            opts['outtmpl'] = str(self.cache_dir / f'{safe_artist} - {safe_title}.%(ext)s')
        
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                # Extract info first
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    logging.error("No video found for query")
                    return None
                
                # Get the first result if it's a search
                if 'entries' in info:
                    info = info['entries'][0]
                
                # Now download
                ydl.download([info['webpage_url']])
                
                # Determine output file path
                file_path = self._get_output_path(info, artist, title)
                
                # Extract metadata
                return {
                    'file_path': str(file_path),
                    'title': title or info.get('title', 'Unknown'),
                    'artist': artist or info.get('artist') or info.get('uploader', 'Unknown'),
                    'duration_sec': info.get('duration', 0),
                    'youtube_id': info.get('id'),
                    'youtube_url': info.get('webpage_url'),
                    'thumbnail_url': info.get('thumbnail'),
                }
        
        except Exception as e:
            logging.error(f"yt-dlp error: {e}")
            return None
    
    def _get_output_path(
        self, 
        info: Dict[str, Any],
        artist: Optional[str] = None,
        title: Optional[str] = None
    ) -> Path:
        """
        Determine the output file path based on info and provided metadata.
        
        Args:
            info: yt-dlp info dict
            artist: Optional artist name
            title: Optional song title
        
        Returns:
            Path to the downloaded file
        """
        if artist and title:
            safe_artist = self._sanitize_filename(artist)
            safe_title = self._sanitize_filename(title)
            filename = f'{safe_artist} - {safe_title}.mp3'
        else:
            # Use yt-dlp's default naming
            artist_name = info.get('artist') or info.get('uploader', 'Unknown')
            song_title = info.get('title', 'Unknown')
            safe_artist = self._sanitize_filename(artist_name)
            safe_title = self._sanitize_filename(song_title)
            filename = f'{safe_artist} - {safe_title}.mp3'
        
        return self.cache_dir / filename
    
    def _sanitize_filename(self, name: str) -> str:
        """
        Sanitize a string for use in filenames.
        
        Args:
            name: String to sanitize
        
        Returns:
            Sanitized string safe for filenames
        """
        # Remove or replace invalid filename characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            name = name.replace(char, '')
        
        # Limit length
        return name[:100].strip()
    
    async def _store_in_db(self, song_info: Dict[str, Any]) -> None:
        """
        Store downloaded song metadata in the database.
        
        Args:
            song_info: Dict with song metadata and file path
        """
        try:
            db = await get_db()
            
            # Generate UUID for the song
            import uuid
            song_uuid = str(uuid.uuid4())
            
            # Prepare song data for database
            song_data = {
                'uuid': song_uuid,
                'title': song_info['title'],
                'artist': song_info['artist'],
                'duration_sec': song_info['duration_sec'],
                'file_path': song_info['file_path'],
                'youtube_id': song_info.get('youtube_id'),
                'youtube_url': song_info.get('youtube_url'),
            }
            
            await db.insert_song(song_data)
            logging.info(f"Stored song in database: {song_uuid}")
        
        except Exception as e:
            logging.error(f"Error storing song in database: {e}")
    
    async def download_multiple(
        self, 
        songs: List[Dict[str, str]]
    ) -> List[Optional[Dict[str, Any]]]:
        """
        Download multiple songs.
        
        Args:
            songs: List of dicts with 'query', 'artist', 'title' keys
        
        Returns:
            List of download results
        """
        results = []
        
        for song in songs:
            query = song.get('query')
            artist = song.get('artist')
            title = song.get('title')
            
            if not query:
                logging.warning(f"Skipping song with no query: {song}")
                results.append(None)
                continue
            
            result = await self.download_song(query, artist, title)
            results.append(result)
            
            # Small delay to avoid rate limiting
            await asyncio.sleep(2)
        
        return results
    
    def get_cached_songs(self) -> List[Path]:
        """
        Get list of all cached song files.
        
        Returns:
            List of Path objects for cached MP3 files
        """
        return list(self.cache_dir.glob('*.mp3'))
    
    def get_cache_size(self) -> int:
        """
        Calculate total size of cached songs in bytes.
        
        Returns:
            Total cache size in bytes
        """
        total_size = 0
        for file_path in self.get_cached_songs():
            if file_path.is_file():
                total_size += file_path.stat().st_size
        return total_size


async def download_song_cli(query: str, artist: str = None, title: str = None):
    """
    CLI helper function to download a song.
    
    Args:
        query: Search query
        artist: Optional artist name
        title: Optional song title
    """
    downloader = SongDownloader()
    result = await downloader.download_song(query, artist, title)
    
    if result:
        print(f"✓ Downloaded: {result['file_path']}")
        print(f"  Artist: {result['artist']}")
        print(f"  Title: {result['title']}")
        print(f"  Duration: {result['duration_sec']}s")
    else:
        print(f"✗ Failed to download: {query}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python song_downloader.py <search_query> [artist] [title]")
        print("Example: python song_downloader.py 'Taylor Swift Shake It Off'")
        print("Example: python song_downloader.py 'shake it off' 'Taylor Swift' 'Shake It Off'")
        sys.exit(1)
    
    query = sys.argv[1]
    artist = sys.argv[2] if len(sys.argv) > 2 else None
    title = sys.argv[3] if len(sys.argv) > 3 else None
    
    asyncio.run(download_song_cli(query, artist, title))

