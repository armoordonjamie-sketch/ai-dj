"""Soundcharts API client for song metadata, lyrics analysis, and popularity.

Uses the official Soundcharts Python SDK: https://github.com/soundcharts/python-sdk
"""
import logging
import asyncio
from typing import Optional, Dict, Any, List
from backend.config import SOUNDCHARTS_APP_ID, SOUNDCHARTS_API_KEY
from backend.db import get_db

try:
    from soundcharts.client import SoundchartsClient as OfficialSoundchartsClient
    SOUNDCHARTS_SDK_AVAILABLE = True
except ImportError:
    SOUNDCHARTS_SDK_AVAILABLE = False
    logging.warning("Soundcharts SDK not installed. Run: pip install soundcharts")


class SoundchartsClient:
    """Wrapper for official Soundcharts Python SDK with async compatibility."""
    
    def __init__(self):
        self.app_id = SOUNDCHARTS_APP_ID
        self.api_key = SOUNDCHARTS_API_KEY
        
        # Validate credentials and SDK availability
        if not SOUNDCHARTS_SDK_AVAILABLE:
            logging.warning("Soundcharts SDK not available. Install with: pip install soundcharts")
            self.enabled = False
            self.client = None
        elif not self.app_id or not self.api_key:
            logging.warning("Soundcharts credentials not configured. Set SOUNDCHARTS_APP_ID and SOUNDCHARTS_API_KEY in .env")
            self.enabled = False
            self.client = None
        else:
            try:
                # Initialize official SDK client
                self.client = OfficialSoundchartsClient(
                    app_id=self.app_id,
                    api_key=self.api_key,
                    console_log_level=logging.WARNING,
                    file_log_level=logging.WARNING,
                    exception_log_level=logging.ERROR
                )
                self.enabled = True
                logging.info("Soundcharts SDK client initialized successfully")
            except Exception as e:
                logging.error(f"Failed to initialize Soundcharts client: {e}")
                self.enabled = False
                self.client = None
    
    async def search_song(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search for songs by name (typo-tolerant).
        
        Uses the official SDK's search.search_song_by_name() method.
        
        Args:
            query: Song name or artist + song name
            limit: Max results to return
        
        Returns:
            List of song results with UUID, title, artist
        """
        if not self.enabled or not self.client:
            logging.debug("Soundcharts client disabled")
            return []
        
        try:
            logging.debug(f"Soundcharts search: query='{query}', limit={limit}")
            
            # The SDK is synchronous, so run it in a thread pool to avoid blocking
            # This prevents the "sync API called from async context" error
            response = await asyncio.to_thread(
                self.client.search.search_song_by_name,
                query,
                limit=limit
            )
            
            # Extract relevant fields from SDK response
            results = []
            if response and 'items' in response:
                for item in response['items']:
                    # The SDK returns creditName for artist, not a nested artist object
                    artist_name = item.get('creditName')
                    if not artist_name and 'artist' in item:
                        artist_obj = item.get('artist')
                        artist_name = artist_obj.get('name') if isinstance(artist_obj, dict) else artist_obj
                    
                    results.append({
                        'uuid': item.get('uuid'),
                        'title': item.get('name'),
                        'artist': artist_name,
                        'release_date': item.get('releaseDate')
                    })
            
            logging.info(f"Soundcharts found {len(results)} songs for '{query}'")
            return results
        
        except Exception as e:
            logging.error(f"Soundcharts search error: {e}")
            import traceback
            logging.debug(traceback.format_exc())
            return []
    
    async def get_song_metadata(self, uuid: str) -> Optional[Dict[str, Any]]:
        """
        Get song metadata including audio features.
        
        Uses the official SDK's song.get_song_metadata() method.
        Note: The SDK doesn't have a separate get_audio_features method.
        
        Args:
            uuid: Soundcharts song UUID
        
        Returns:
            Dict with song metadata or None
        """
        if not self.enabled or not self.client:
            return None
        
        try:
            # Use official SDK with asyncio.to_thread
            data = await asyncio.to_thread(
                self.client.song.get_song_metadata,
                uuid
            )
            
            if data:
                # #region agent log
                import json;open(r'c:\Users\JamiePC\Desktop\ai-djv2\.cursor\debug.log','a').write(json.dumps({"location":"soundcharts.py:get_song_metadata:data_received","message":"Metadata received","data":{"uuid":uuid,"has_audio":('audio' in data.get('object',{})) if isinstance(data,dict) else False,"data_keys":list(data.keys()) if isinstance(data,dict) else []},"timestamp":__import__('time').time()*1000,"sessionId":"debug-session","hypothesisId":"H9"})+'\n')
                # #endregion
                
                # Extract audio features if present in metadata
                # The SDK returns nested structure: data['object']['audio']
                obj = data.get('object', {}) if isinstance(data, dict) else {}
                if 'audio' in obj:
                    features = obj['audio']
                    # #region agent log
                    import json;open(r'c:\Users\JamiePC\Desktop\ai-djv2\.cursor\debug.log','a').write(json.dumps({"location":"soundcharts.py:get_song_metadata:before_db_save","message":"Attempting to save features","data":{"uuid":uuid,"features_keys":list(features.keys()) if isinstance(features,dict) else []},"timestamp":__import__('time').time()*1000,"sessionId":"debug-session","hypothesisId":"H9,H10"})+'\n')
                    # #endregion
                    try:
                        db = await get_db()
                        await db.insert_song_features(uuid, features)
                        # #region agent log
                        import json;open(r'c:\Users\JamiePC\Desktop\ai-djv2\.cursor\debug.log','a').write(json.dumps({"location":"soundcharts.py:get_song_metadata:db_save_success","message":"Features saved to DB","data":{"uuid":uuid},"timestamp":__import__('time').time()*1000,"sessionId":"debug-session","hypothesisId":"H9"})+'\n')
                        # #endregion
                    except Exception as db_err:
                        # #region agent log
                        import json;open(r'c:\Users\JamiePC\Desktop\ai-djv2\.cursor\debug.log','a').write(json.dumps({"location":"soundcharts.py:get_song_metadata:db_save_error","message":"DB save failed","data":{"uuid":uuid,"error":str(db_err)},"timestamp":__import__('time').time()*1000,"sessionId":"debug-session","hypothesisId":"H10,H11"})+'\n')
                        # #endregion
                        logging.error(f"Failed to save song features: {db_err}")
            
            return data
        
        except Exception as e:
            logging.error(f"Soundcharts metadata error for {uuid}: {e}")
            return None
    
    async def get_lyrics_analysis(self, uuid: str) -> Optional[Dict[str, Any]]:
        """
        Get lyrics analysis (themes, moods, narrative style, scores).
        
        Uses the official SDK's song.get_lyrics_analysis() method.
        
        Args:
            uuid: Soundcharts song UUID
        
        Returns:
            Dict with lyrics analysis or None
        """
        if not self.enabled or not self.client:
            return None
        
        try:
            # Use official SDK with asyncio.to_thread
            data = await asyncio.to_thread(
                self.client.song.get_lyrics_analysis,
                uuid
            )
            
            if data:
                # Convert lists to JSON strings for storage
                analysis = {
                    'themes': str(data.get('themes', [])),
                    'moods': str(data.get('moods', [])),
                    'brands': str(data.get('brands', [])),
                    'locations': str(data.get('locations', [])),
                    'cultural_ref_people': str(data.get('cultural_references', {}).get('people', [])),
                    'cultural_ref_non_people': str(data.get('cultural_references', {}).get('non_people', [])),
                    'narrative_style': data.get('narrative_style'),
                    'emotional_intensity_score': data.get('scores', {}).get('emotional_intensity'),
                    'imagery_score': data.get('scores', {}).get('imagery'),
                    'complexity_score': data.get('scores', {}).get('complexity'),
                    'rhyme_scheme_score': data.get('scores', {}).get('rhyme_scheme'),
                    'repetitiveness_score': data.get('scores', {}).get('repetitiveness')
                }
                
                # Store in database
                db = await get_db()
                await db.insert_lyrics_analysis(uuid, analysis)
            
            return data
        
        except Exception as e:
            logging.error(f"Soundcharts lyrics error for {uuid}: {e}")
            return None
    
    async def get_popularity(self, uuid: str, platform: str = "spotify") -> Optional[Dict[str, Any]]:
        """
        Get song popularity on streaming platforms.
        
        Uses the official SDK's song.get_popularity() method.
        
        Args:
            uuid: Soundcharts song UUID
            platform: Platform name (spotify, tidal, deezer)
        
        Returns:
            Dict with popularity data or None
        """
        if not self.enabled or not self.client:
            return None
        
        try:
            # Use official SDK with asyncio.to_thread
            data = await asyncio.to_thread(
                self.client.song.get_popularity,
                uuid,
                platform=platform
            )
            
            return data
        
        except Exception as e:
            logging.error(f"Soundcharts popularity error for {uuid} on {platform}: {e}")
            return None
    
    async def get_song_info(self, uuid: str) -> Optional[Dict[str, Any]]:
        """
        Get basic song information.
        
        Uses the official SDK's song.get_song_metadata() method.
        
        Args:
            uuid: Soundcharts song UUID
        
        Returns:
            Dict with song info or None
        """
        if not self.enabled or not self.client:
            return None
        
        try:
            # Use official SDK with asyncio.to_thread
            data = await asyncio.to_thread(
                self.client.song.get_song_metadata,
                uuid
            )
            
            if data:
                # Store basic info in database
                song_data = {
                    'uuid': uuid,
                    'title': data.get('name'),
                    'artist': data.get('artist', {}).get('name') if isinstance(data.get('artist'), dict) else data.get('creditName'),
                    'release_date': data.get('releaseDate') or data.get('release_date'),
                    'language_code': data.get('language'),
                    'explicit': 1 if data.get('explicit') else 0,
                    'duration_sec': data.get('duration_ms', 0) / 1000.0 if data.get('duration_ms') else None
                }
                
                db = await get_db()
                await db.insert_song(song_data)
            
            return data
        
        except Exception as e:
            logging.error(f"Soundcharts song info error for {uuid}: {e}")
            return None


# Global client instance
_soundcharts_client: Optional[SoundchartsClient] = None


def get_soundcharts_client() -> SoundchartsClient:
    """Get or create global Soundcharts client."""
    global _soundcharts_client
    if _soundcharts_client is None:
        _soundcharts_client = SoundchartsClient()
    return _soundcharts_client

