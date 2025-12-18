"""Cache management for song files with 50GB limit and least-played eviction."""
import logging
import os
from pathlib import Path
from typing import Optional
from backend.db import get_db
from backend.config import SONG_CACHE_DIR, CACHE_MAX_BYTES


class CacheManager:
    """Manages local song cache with size limits and eviction."""
    
    def __init__(self):
        self.cache_dir = SONG_CACHE_DIR
        self.max_bytes = CACHE_MAX_BYTES
        
        # Ensure cache directory exists
        Path(self.cache_dir).mkdir(parents=True, exist_ok=True)
    
    async def get_song_path(self, song_uuid: str) -> Optional[str]:
        """
        Get local path for a song, downloading if necessary.
        
        Args:
            song_uuid: Soundcharts song UUID
        
        Returns:
            Local file path or None if unavailable
        """
        db = await get_db()
        song = await db.get_song(song_uuid)
        
        if not song:
            logging.warning(f"Song {song_uuid} not in database")
            return None
        
        local_path = song.get('local_path')
        
        # Check if file exists
        if local_path and os.path.exists(local_path):
            return local_path
        
        # File not cached - would need to download
        # For demo: check if file exists in song-cache directory
        potential_paths = [
            os.path.join('backend/song-cache', f"{song.get('title', '')}.mp3"),
            os.path.join('backend/song-cache', f"{song.get('artist', '')} - {song.get('title', '')}.mp3")
        ]
        
        for path in potential_paths:
            if os.path.exists(path):
                # Update database with local path
                filesize = os.path.getsize(path)
                await db.insert_song({
                    'uuid': song_uuid,
                    'local_path': path,
                    'filesize_bytes': filesize,
                    **song
                })
                
                # Check cache size and evict if needed
                await self.enforce_cache_limit()
                
                return path
        
        logging.warning(f"Song file not found for {song_uuid}")
        return None
    
    async def enforce_cache_limit(self):
        """Evict least-played songs if cache exceeds limit."""
        db = await get_db()
        current_size = await db.get_cache_size()
        
        if current_size > self.max_bytes:
            logging.info(f"Cache size {current_size} exceeds limit {self.max_bytes}, evicting...")
            evicted = await db.evict_least_played_songs(self.max_bytes)
            logging.info(f"Evicted {len(evicted)} songs: {evicted}")
    
    async def get_cache_stats(self) -> dict:
        """Get current cache statistics."""
        db = await get_db()
        current_size = await db.get_cache_size()
        
        return {
            'used_bytes': current_size,
            'limit_bytes': self.max_bytes,
            'usage_percent': (current_size / self.max_bytes * 100) if self.max_bytes > 0 else 0
        }


# Global cache manager instance
_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """Get or create global cache manager."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager

