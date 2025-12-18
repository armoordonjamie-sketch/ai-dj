"""LangGraph orchestration graph and state types for AI DJ multi-agent planning using the current LangGraph StateGraph API."""
import asyncio
import logging
import os
import json
from typing import TypedDict, List, Optional, Dict, Any
from datetime import datetime

try:
    from langgraph.graph import StateGraph, START, END
except ImportError:
    StateGraph = None
    START = None
    END = None

from backend.integrations.soundcharts import get_soundcharts_client
from backend.integrations.openrouter import get_openrouter_client
from backend.integrations.elevenlabs import get_elevenlabs_client
from backend.db import get_db
from backend.config import SEGMENT_DIR, USER_CONTEXT_FILE
from backend.song_downloader import SongDownloader
from backend.cache_manager import get_cache_manager
from backend.ai_analyzer import analyze_tracks_async
from backend.dj_mix import create_dj_mix
import random


def load_user_context() -> Dict[str, Any]:
    """Load and parse user context file to extract preferences."""
    context = {
        "name": "User",
        "music_preferences": [],
        "genres": ["pop"],
        "mood": 0.7,
        "raw_text": ""
    }
    
    try:
        if os.path.exists(USER_CONTEXT_FILE):
            with open(USER_CONTEXT_FILE, 'r', encoding='utf-8') as f:
                raw_text = f.read()
                context["raw_text"] = raw_text
                
                # Extract name from first line
                lines = raw_text.strip().split('\n')
                if lines and 'User:' in lines[0]:
                    name_part = lines[0].split('User:')[1].strip()
                    # Get first word/name before parenthesis
                    context["name"] = name_part.split('(')[0].strip()
                
                # Parse music preferences section
                in_music_section = False
                for line in lines:
                    if 'Music Preferences:' in line:
                        in_music_section = True
                        continue
                    if in_music_section:
                        if line.startswith('DJ ') or line.startswith('\n') or ':' in line:
                            in_music_section = False
                            continue
                        if line.strip().startswith('-'):
                            pref = line.strip().lstrip('-').strip()
                            if pref:
                                context["music_preferences"].append(pref)
                
                logging.info(f"Loaded user context for: {context['name']}, preferences: {context['music_preferences'][:3]}")
    except Exception as e:
        logging.warning(f"Failed to load user context: {e}, using defaults")
    
    return context


async def get_ai_search_query(user_context: Dict[str, Any], history: List[Dict[str, Any]] = None) -> str:
    """Use AI to generate a search query based on user preferences."""
    openrouter = get_openrouter_client()
    
    # Fallback artist names that work with the Soundcharts API
    # These are real artist names, not genre descriptions
    FALLBACK_ARTISTS = [
        "Queen", "ABBA", "Dua Lipa", "Elton John", "Wham", 
        "Harry Styles", "The Weeknd", "Fleetwood Mac", "Bee Gees",
        "Culture Club", "Eurythmics", "Ed Sheeran", "Adele"
    ]
    
    if not openrouter.enabled:
        # Fallback - use a random known artist
        return random.choice(FALLBACK_ARTISTS)
    
    try:
        response = await openrouter.generate_search_queries(
            user_preferences=user_context.get("music_preferences", []),
            raw_context=user_context.get("raw_text", ""),
            history=history,
            count=5
        )
        
        if response and response.get('parsed'):
            queries = response['parsed'].get('queries', [])
            if queries:
                # Validate queries - make sure they're not generic genre descriptions
                # Allow 'latest', 'popular', 'top' which are now permitted
                valid_queries = [q for q in queries if len(q.split()) <= 6 and not any(
                    bad in q.lower() for bad in ['genre', 'music', 'anthems', 'era', '70s', '80s', '90s']
                )]
                if valid_queries:
                    return random.choice(valid_queries)
                # If AI still generated bad queries, use fallback
                logging.warning(f"AI generated invalid queries: {queries}, using fallback")
        
        # Fallback to known artist
        return random.choice(FALLBACK_ARTISTS)
    
    except Exception as e:
        logging.warning(f"AI search query generation failed: {e}")
        return random.choice(FALLBACK_ARTISTS)


# Define DJState schema type
class NowPlayingSegment(TypedDict):
    track_id: str
    start_time: float
    duration: float

class DecisionStep(TypedDict):
    step: str
    detail: str

class DJState(TypedDict):
    now_playing: List[NowPlayingSegment]
    decision_trace: List[DecisionStep]
    session_id: Optional[str]
    segment_queue_size: Optional[int]
    selected_song_uuid: Optional[str]
    song_a_uuid: Optional[str]  # Previous song for transitions
    song_b_uuid: Optional[str]  # Next song for transitions
    song_a_path: Optional[str]  # File path for song A
    song_b_path: Optional[str]  # File path for song B
    transition_plan: Optional[Dict[str, Any]]
    speech_script: Optional[str]
    tts_audio_path: Optional[str]
    rendered_segment_path: Optional[str]
    download_status: Optional[str]  # Status of download operations


# Agent node implementations
async def bootstrap(state: DJState) -> DJState:
    """Bootstrap to set an initial empty DJState."""
    logging.info("Bootstrap: Initializing DJ state")
    return {
        "now_playing": state.get("now_playing", []),
        "decision_trace": state.get("decision_trace", []),
        "session_id": state.get("session_id"),
        "segment_queue_size": state.get("segment_queue_size", 0)
    }


async def InitialSongSelectorAgent(state: DJState) -> DJState:
    """Select initial song when play is pressed - downloads and saves metadata."""
    logging.info("InitialSongSelectorAgent: Selecting initial song")
    
    try:
        db = await get_db()
        soundcharts = get_soundcharts_client()
        openrouter = get_openrouter_client()
        
        session_id = state.get("session_id", "")
        
        # Load user context for personalized search
        user_context = load_user_context()
        
        # Check if Soundcharts is available
        if not soundcharts.enabled:
            logging.warning("Soundcharts disabled - cannot search for songs")
            return {**state, "selected_song_uuid": None, "download_status": "soundcharts_disabled"}
        
        # Let AI generate search query based on preferences
        search_query = await get_ai_search_query(user_context, history=[])
        logging.info(f"AI generated search query: {search_query}")
        
        # Search for songs based on AI-selected query
        search_results = await soundcharts.search_song(search_query, limit=10)
        
        if not search_results:
            logging.warning(f"No songs found for '{search_query}', trying another AI query")
            # Let AI try another query
            fallback_query = await get_ai_search_query(user_context, history=[])
            search_results = await soundcharts.search_song(fallback_query, limit=10)
        
        if not search_results:
            logging.warning("No songs found from Soundcharts")
            return {**state, "selected_song_uuid": None, "download_status": "no_results"}
        
        # Use LLM to select track (or fallback to first) - pass user context
        user_controls = {
            "mood": user_context.get("mood", 0.7),
            "genres": user_context.get("genres", ["pop"]),
            "prompt": None,
            "user_preferences": user_context.get("music_preferences", [])
        }
        
        history = []  # No history for initial song
        
        llm_response = await openrouter.generate_track_selection(
            user_controls=user_controls,
            history=history,
            available_songs=search_results,
            thinking_budget=2000
        )
        
        if llm_response and llm_response.get('parsed'):
            selected_uuid = llm_response['parsed'].get('selected_uuid')
            rationale = llm_response['parsed'].get('rationale', '')
        else:
            # Fallback: pick first result
            selected_uuid = search_results[0]['uuid']
            rationale = "Fallback selection"
        
        # Store LLM trace (non-fatal if it fails)
        try:
            await db.insert_llm_trace({
                'session_id': session_id,
                'agent_name': 'InitialSongSelectorAgent',
                'prompt': str(user_controls),
                'response': llm_response.get('content') if llm_response else '',
                'model': llm_response.get('model') if llm_response else 'fallback',
                'thinking_budget': 2000
            })
        except Exception as trace_err:
            logging.warning(f"Failed to store LLM trace (non-fatal): {trace_err}")
        
        # Add decision trace
        decision_trace = state.get("decision_trace", [])
        decision_trace.append({
            "step": "initial_track_selection",
            "detail": rationale
        })
        
        logging.info(f"Selected initial track: {selected_uuid}")
        return {
            **state,
            "selected_song_uuid": selected_uuid,
            "song_b_uuid": selected_uuid,  # This will be the first song
            "decision_trace": decision_trace,
            "download_status": "selected"
        }
    
    except Exception as e:
        logging.error(f"InitialSongSelectorAgent error: {e}")
        return {**state, "selected_song_uuid": None, "download_status": f"error: {str(e)}"}


async def DownloadSongTool(state: DJState) -> DJState:
    """Download song if not cached, using SongDownloader."""
    logging.info("DownloadSongTool: Checking cache and downloading if needed")
    
    try:
        selected_uuid = state.get("selected_song_uuid")
        if not selected_uuid:
            logging.warning("No selected song UUID")
            return {**state, "download_status": "no_uuid"}
        
        cache_manager = get_cache_manager()
        db = await get_db()
        soundcharts = get_soundcharts_client()
        
        # Check if song is already cached
        song_path = await cache_manager.get_song_path(selected_uuid)
        
        if song_path and os.path.exists(song_path):
            logging.info(f"Song already cached: {song_path}")
            return {
                **state,
                "song_b_path": song_path,
                "download_status": "cached"
            }
        
        # Get song info from database or Soundcharts
        song = await db.get_song(selected_uuid)
        if not song:
            # Fetch from Soundcharts
            metadata = await soundcharts.get_song_metadata(selected_uuid)
            if metadata:
                # Extract song info from metadata
                obj = metadata.get('object', {}) if isinstance(metadata, dict) else {}
                title = obj.get('name', 'Unknown')
                artist = obj.get('creditName', 'Unknown')
                
                # Save to database
                await db.insert_song({
                    'uuid': selected_uuid,
                    'title': title,
                    'artist': artist,
                    'local_path': None
                })
                song = await db.get_song(selected_uuid)
        
        if not song:
            logging.error(f"Could not get song info for {selected_uuid}")
            return {**state, "download_status": "no_song_info"}
        
        # Download using SongDownloader
        downloader = SongDownloader()
        title = song.get('title', 'Unknown')
        artist = song.get('artist', 'Unknown')
        query = f"{artist} {title}"
        
        logging.info(f"Downloading song: {query}")
        download_result = await downloader.download_song(query, artist, title)
        
        if download_result and download_result.get('file_path'):
            file_path = download_result['file_path']
            
            # Update database with local path and Soundcharts UUID
            # Note: SongDownloader creates its own UUID, but we want to use Soundcharts UUID
            filesize = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            await db.insert_song({
                'uuid': selected_uuid,  # Use Soundcharts UUID
                'title': title,
                'artist': artist,
                'local_path': file_path,
                'filesize_bytes': filesize,
                'duration_sec': download_result.get('duration_sec', song.get('duration_sec'))
            })
            
            logging.info(f"Downloaded song to: {file_path}")
            return {
                **state,
                "song_b_path": file_path,
                "download_status": "downloaded"
            }
        else:
            logging.error(f"Download failed for {selected_uuid}")
            return {**state, "download_status": "download_failed"}
    
    except Exception as e:
        logging.error(f"DownloadSongTool error: {e}")
        return {**state, "download_status": f"error: {str(e)}"}


async def SaveMetadataNode(state: DJState) -> DJState:
    """Save song metadata to database after download."""
    logging.info("SaveMetadataNode: Saving metadata")
    
    try:
        selected_uuid = state.get("selected_song_uuid")
        if not selected_uuid:
            return state
        
        db = await get_db()
        soundcharts = get_soundcharts_client()
        
        # Ensure song record exists with local_path
        song_b_path = state.get("song_b_path")
        if song_b_path and os.path.exists(song_b_path):
            # Get existing song record
            song = await db.get_song(selected_uuid)
            
            # If song doesn't exist or doesn't have local_path, update it
            if not song or not song.get('local_path'):
                # Get song info from state or database
                title = song.get('title', 'Unknown') if song else 'Unknown'
                artist = song.get('artist', 'Unknown') if song else 'Unknown'
                
                # If we don't have song info, fetch from Soundcharts
                if not song:
                    metadata = await soundcharts.get_song_metadata(selected_uuid)
                    if metadata:
                        obj = metadata.get('object', {}) if isinstance(metadata, dict) else {}
                        title = obj.get('name', 'Unknown')
                        artist = obj.get('creditName', 'Unknown')
                
                # Save/update song with local_path
                filesize = os.path.getsize(song_b_path) if os.path.exists(song_b_path) else 0
                await db.insert_song({
                    'uuid': selected_uuid,
                    'title': title,
                    'artist': artist,
                    'local_path': song_b_path,
                    'filesize_bytes': filesize
                })
                logging.info(f"Saved song record with local_path: {song_b_path}")
        
        # Fetch and save metadata features if not already saved
        song_features = await db.get_song_features(selected_uuid)
        if not song_features:
            await soundcharts.get_song_metadata(selected_uuid)
        
        logging.info(f"Metadata saved for {selected_uuid}")
        return state
    
    except Exception as e:
        logging.error(f"SaveMetadataNode error: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return state


async def TrackSelectorAgent(state: DJState) -> DJState:
    """Select next track based on user controls and history."""
    logging.info("TrackSelectorAgent: Selecting next track")
    
    try:
        db = await get_db()
        soundcharts = get_soundcharts_client()
        openrouter = get_openrouter_client()
        
        # Get recent play history
        session_id = state.get("session_id", "")
        session_id = state.get("session_id", "")
        # Use global history to avoid repeating songs across sessions
        history = await db.get_global_recent_plays(limit=50)
        
        # Load user context for personalized search
        user_context = load_user_context()
        
        # Check if Soundcharts is available
        if not soundcharts.enabled:
            logging.warning("Soundcharts disabled - cannot search for songs")
            logging.info("Using fallback: checking local song cache")
            # TODO: Scan local song cache directory for available songs
            return {**state, "selected_song_uuid": None}
        
        # Let AI generate search query based on preferences and history
        search_query = await get_ai_search_query(user_context, history)
        logging.info(f"AI generated search query: {search_query}")
        
        # Search for songs based on AI-selected query
        search_results = await soundcharts.search_song(search_query, limit=10)
        
        if not search_results:
            logging.warning(f"No songs found for '{search_query}', trying another AI query")
            fallback_query = await get_ai_search_query(user_context, history)
            search_results = await soundcharts.search_song(fallback_query, limit=10)
        
        if not search_results:
            logging.warning("No songs found from Soundcharts")
            logging.info("This may indicate API access issues - check credentials")
            return {**state, "selected_song_uuid": None}
        
        # Use LLM to select track - pass user context
        user_controls = {
            "mood": user_context.get("mood", 0.7),
            "genres": user_context.get("genres", ["pop"]),
            "prompt": None,
            "user_preferences": user_context.get("music_preferences", [])
        }
        
        llm_response = await openrouter.generate_track_selection(
            user_controls=user_controls,
            history=history,
            available_songs=search_results,
            thinking_budget=2000
        )
        
        if llm_response and llm_response.get('parsed'):
            selected_uuid = llm_response['parsed'].get('selected_uuid')
            rationale = llm_response['parsed'].get('rationale', '')
            
            # Store LLM trace (non-fatal if it fails)
            try:
                await db.insert_llm_trace({
                    'session_id': session_id,
                    'agent_name': 'TrackSelectorAgent',
                    'prompt': str(user_controls),
                    'response': llm_response.get('content'),
                    'model': llm_response.get('model'),
                    'thinking_budget': 2000
                })
            except Exception as trace_err:
                logging.warning(f"Failed to store LLM trace (non-fatal): {trace_err}")
            
            # Add decision trace
            decision_trace = state.get("decision_trace", [])
            decision_trace.append({
                "step": "track_selection",
                "detail": rationale
            })
            
            logging.info(f"Selected track: {selected_uuid}")
            return {**state, "selected_song_uuid": selected_uuid, "decision_trace": decision_trace}
        else:
            # Fallback: pick first result
            selected_uuid = search_results[0]['uuid']
            logging.info(f"Fallback selection: {selected_uuid}")
            return {**state, "selected_song_uuid": selected_uuid}
    
    except Exception as e:
        logging.error(f"TrackSelectorAgent error: {e}")
        return state


async def PlanningAgent(state: DJState) -> DJState:
    """Planning agent that runs during playback - selects next song and checks cache."""
    logging.info("PlanningAgent: Planning next transition")
    
    try:
        db = await get_db()
        soundcharts = get_soundcharts_client()
        openrouter = get_openrouter_client()
        
        session_id = state.get("session_id", "")
        
        # Load user context once for personalized selection
        session_id = state.get("session_id", "")
        
        # Load user context once for personalized selection
        user_context = load_user_context()
        
        # Get recent play history to find previous song (song A)
        # For song A (transition source), we specifically need the LAST played song in THIS session
        session_history = await db.get_recent_plays(session_id, limit=5)
        
        # For avoiding repeats, we need GLOBAL history
        global_history = await db.get_global_recent_plays(limit=50)
        
        song_a_uuid = None
        if session_history and len(session_history) > 0:
            song_a_uuid = session_history[0].get('song_uuid')
            state = {**state, "song_a_uuid": song_a_uuid}
        
        # Get list of recently played UUIDs to exclude (from global history)
        recently_played_uuids = [h.get('song_uuid') for h in global_history if h.get('song_uuid')]
        
        # First, try to get songs from database cache
        cached_songs = await db.get_cached_songs(limit=20, exclude_uuids=recently_played_uuids)
        
        search_results = []
        if cached_songs and len(cached_songs) >= 1:
            # Use cached songs from database - convert to format expected by LLM
            logging.info(f"Using {len(cached_songs)} cached songs from database")
            search_results = [
                {
                    'uuid': song['uuid'],
                    'name': song.get('title', 'Unknown'),
                    'creditName': song.get('artist', 'Unknown'),
                    'imageUrl': None,
                    'releaseDate': song.get('release_date')
                }
                for song in cached_songs
            ]
        else:
            # Not enough cached songs, fall back to Soundcharts API (but cache results)
            logging.info(f"Only {len(cached_songs) if cached_songs else 0} cached songs available, using Soundcharts API")
            if not soundcharts.enabled:
                logging.warning("Soundcharts disabled and insufficient cached songs")
                return {**state, "selected_song_uuid": None}
            
            # Let AI generate search query based on user preferences
            search_query = await get_ai_search_query(user_context, session_history)
            logging.info(f"AI generated search query for planning: {search_query}")
            
            search_results = await soundcharts.search_song(search_query, limit=10)
            if not search_results:
                return {**state, "selected_song_uuid": None}
        
        # Use LLM to select next track - pass user context
        user_controls = {
            "mood": user_context.get("mood", 0.7),
            "genres": user_context.get("genres", ["pop"]),
            "prompt": None,
            "user_preferences": user_context.get("music_preferences", [])
        }
        
        llm_response = await openrouter.generate_track_selection(
            user_controls=user_controls,
            history=session_history,
            available_songs=search_results,
            thinking_budget=2000
        )
        
        if llm_response and llm_response.get('parsed'):
            selected_uuid = llm_response['parsed'].get('selected_uuid')
            rationale = llm_response['parsed'].get('rationale', '')
        else:
            selected_uuid = search_results[0]['uuid']
            rationale = "Fallback selection"
        
        # Store LLM trace (non-fatal if it fails)
        try:
            await db.insert_llm_trace({
                'session_id': session_id,
                'agent_name': 'PlanningAgent',
                'prompt': str(user_controls),
                'response': llm_response.get('content') if llm_response else '',
                'model': llm_response.get('model') if llm_response else 'fallback',
                'thinking_budget': 2000
            })
        except Exception as trace_err:
            logging.warning(f"Failed to store LLM trace (non-fatal): {trace_err}")
        
        decision_trace = state.get("decision_trace", [])
        decision_trace.append({
            "step": "planning_next_track",
            "detail": rationale
        })
        
        logging.info(f"PlanningAgent selected: {selected_uuid}")
        return {
            **state,
            "selected_song_uuid": selected_uuid,
            "song_b_uuid": selected_uuid,
            "decision_trace": decision_trace
        }
    
    except Exception as e:
        logging.error(f"PlanningAgent error: {e}")
        return state


async def CheckCacheTool(state: DJState) -> DJState:
    """Check if songs are cached, set paths."""
    logging.info("CheckCacheTool: Checking cache")
    
    try:
        cache_manager = get_cache_manager()
        
        # Check song A (previous song)
        song_a_uuid = state.get("song_a_uuid")
        if song_a_uuid:
            song_a_path = await cache_manager.get_song_path(song_a_uuid)
            if song_a_path and os.path.exists(song_a_path):
                state = {**state, "song_a_path": song_a_path}
                logging.info(f"Song A cached: {song_a_path}")
        
        # Check song B (next song)
        selected_uuid = state.get("selected_song_uuid")
        if selected_uuid:
            song_b_path = await cache_manager.get_song_path(selected_uuid)
            if song_b_path and os.path.exists(song_b_path):
                state = {**state, "song_b_path": song_b_path}
                logging.info(f"Song B cached: {song_b_path}")
            else:
                # Will be downloaded by DownloadIfNeededTool
                logging.info(f"Song B not cached: {selected_uuid}")
        
        return state
    
    except Exception as e:
        logging.error(f"CheckCacheTool error: {e}")
        return state


async def DownloadIfNeededTool(state: DJState) -> DJState:
    """Download song if not cached."""
    return await DownloadSongTool(state)


async def TransitionPlannerAgent(state: DJState) -> DJState:
    """Plan transition between current and next song using audio-based AI analysis."""
    logging.info("TransitionPlannerAgent: Planning transition with audio analysis")
    
    try:
        song_a_uuid = state.get("song_a_uuid")
        song_b_uuid = state.get("song_b_uuid")
        
        if not song_b_uuid:
            logging.warning("No song B, skipping transition planning")
            return state
        
        db = await get_db()
        
        # Get song file paths
        song_a_path = state.get("song_a_path")
        song_b_path = state.get("song_b_path")
        has_song_a = bool(song_a_uuid and song_a_path and os.path.exists(song_a_path))
        
        if not song_b_path or not os.path.exists(song_b_path):
            logging.warning("No valid song B path for transition")
            return state
        
        # Use audio-based AI analysis for transition planning
        if has_song_a:
            logging.info(f"Analyzing audio: {song_a_path} -> {song_b_path}")
            transition_plan = await analyze_tracks_async(song_a_path, song_b_path)
        else:
            # No song A - use default intro plan
            logging.info("No song A - using default intro transition")
            transition_plan = {
                "transition_type": "blend",
                "transition_start": None,
                "crossfade_duration": 10.0,
                "tts_start_offset": 5.0,
                "analysis": "First song in set - no transition needed"
            }
        
        # Store analysis trace (non-fatal if it fails)
        session_id = state.get("session_id", "")
        try:
            await db.insert_llm_trace({
                'session_id': session_id,
                'agent_name': 'TransitionPlannerAgent',
                'prompt': f"audio_analysis: song_a={song_a_path}, song_b={song_b_path}",
                'response': json.dumps(transition_plan),
                'model': 'google/gemini-2.0-flash-001',
                'thinking_budget': 0  # Audio analysis doesn't use thinking budget
            })
        except Exception as trace_err:
            logging.warning(f"Failed to store LLM trace (non-fatal): {trace_err}")
        
        transition_type = transition_plan.get('transition_type', 'blend')
        logging.info(f"Transition plan: {transition_type} - {transition_plan.get('analysis', 'No analysis')[:100]}")
        return {**state, "transition_plan": transition_plan}
    
    except Exception as e:
        logging.error(f"TransitionPlannerAgent error: {e}")
        import traceback
        logging.error(traceback.format_exc())
        
        # Fallback to default blend
        transition_plan = {
            "transition_type": "blend",
            "transition_start": 190.0,
            "crossfade_duration": 10.0,
            "tts_start_offset": 5.0,
            "analysis": f"Error fallback: {str(e)}"
        }
        return {**state, "transition_plan": transition_plan}


async def InitialSpeechWriterAgent(state: DJState) -> DJState:
    """Generate intro speech for the first song when DJ starts."""
    logging.info("InitialSpeechWriterAgent: Writing intro speech for first song")
    
    try:
        openrouter = get_openrouter_client()
        from backend.config import USER_CONTEXT_FILE, THINKING_BUDGETS
        
        # Load user context file
        user_context_text = "Generic user"
        try:
            if os.path.exists(USER_CONTEXT_FILE):
                with open(USER_CONTEXT_FILE, 'r') as f:
                    user_context_text = f.read()
            else:
                logging.warning(f"User context file not found: {USER_CONTEXT_FILE}")
        except Exception as e:
            logging.error(f"Failed to load user context: {e}")
        
        # Get song info for the intro
        selected_uuid = state.get("selected_song_uuid")
        song_info = {
            "uuid": selected_uuid,
            "title": "Unknown",
            "artist": "Unknown"
        }
        
        # Try to get song details from database
        if selected_uuid:
            try:
                db = await get_db()
                song = await db.get_song(selected_uuid)
                if song:
                    song_info["title"] = song.get("title", "Unknown")
                    song_info["artist"] = song.get("artist", "Unknown")
            except Exception as e:
                logging.warning(f"Could not fetch song details: {e}")
        
        thinking_budget = THINKING_BUDGETS.get('speech_writer', 3500)
        
        llm_response = await openrouter.generate_dj_intro_speech(
            song_info=song_info,
            user_context=user_context_text,
            thinking_budget=thinking_budget
        )
        
        if llm_response and llm_response.get('parsed'):
            speech_text = llm_response['parsed'].get('text', '')
            logging.info(f"DJ intro: {speech_text}")
            return {**state, "speech_script": speech_text}
        else:
            # Fallback intro
            logging.warning("LLM intro generation failed, using fallback")
            return {**state, "speech_script": "Alright, let's get this started!"}
    
    except Exception as e:
        logging.error(f"InitialSpeechWriterAgent error: {e}")
        # Still provide a fallback intro
        return {**state, "speech_script": "Let's go!"}


async def SpeechWriterAgent(state: DJState) -> DJState:
    """Decide if DJ should talk and write script."""
    logging.info("SpeechWriterAgent: Checking if DJ should speak")
    
    try:
        # Always generate speech for transitions (can be made configurable later)
        # For now, generate speech for every transition to make DJ more engaging
        should_speak = True
        
        if not should_speak:
            logging.info("DJ not speaking this time")
            return {**state, "speech_script": None}
        
        openrouter = get_openrouter_client()
        from backend.config import USER_CONTEXT_FILE, THINKING_BUDGETS
        
        # Load user context file
        user_context = "Generic user"
        try:
            if os.path.exists(USER_CONTEXT_FILE):
                with open(USER_CONTEXT_FILE, 'r') as f:
                    user_context = f.read()
            else:
                logging.warning(f"User context file not found: {USER_CONTEXT_FILE}")
        except Exception as e:
            logging.error(f"Failed to load user context: {e}")
        
        context = {
            "selected_song": state.get("selected_song_uuid"),
            "transition_type": state.get("transition_plan", {}).get("transition_type"),
            "song_b_uuid": state.get("song_b_uuid"),
            "song_a_uuid": state.get("song_a_uuid")
        }
        
        thinking_budget = THINKING_BUDGETS.get('speech_writer', 3500)
        
        llm_response = await openrouter.generate_dj_speech(
            context=context,
            user_context=user_context,
            thinking_budget=thinking_budget
        )
        
        if llm_response and llm_response.get('parsed'):
            speech_text = llm_response['parsed'].get('text', '')
            logging.info(f"DJ says: {speech_text}")
            return {**state, "speech_script": speech_text}
        else:
            return {**state, "speech_script": None}
    
    except Exception as e:
        logging.error(f"SpeechWriterAgent error: {e}")
        return state


async def ParallelPlanningNode(state: DJState) -> DJState:
    """Run transition planning and speech writing concurrently."""
    logging.info("ParallelPlanningNode: Running transition and speech planning concurrently")
    
    try:
        # Run both agents concurrently
        transition_task = TransitionPlannerAgent(state)
        speech_task = SpeechWriterAgent(state)
        
        # Wait for both to complete
        transition_result, speech_result = await asyncio.gather(
            transition_task, speech_task, return_exceptions=True
        )
        
        # Handle exceptions
        if isinstance(transition_result, Exception):
            logging.error(f"Transition planning failed: {transition_result}")
            transition_result = state
        
        if isinstance(speech_result, Exception):
            logging.error(f"Speech writing failed: {speech_result}")
            speech_result = state
        
        # Merge results
        merged_state = {
            **state,
            "transition_plan": transition_result.get("transition_plan") if isinstance(transition_result, dict) else state.get("transition_plan"),
            "speech_script": speech_result.get("speech_script") if isinstance(speech_result, dict) else state.get("speech_script")
        }
        
        logging.info("ParallelPlanningNode: Completed both tasks")
        return merged_state
    
    except Exception as e:
        logging.error(f"ParallelPlanningNode error: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return state


async def TTSAgent(state: DJState) -> DJState:
    """Synthesize speech using ElevenLabs."""
    logging.info("TTSAgent: Synthesizing speech")
    
    try:
        speech_script = state.get("speech_script")
        if not speech_script:
            logging.info("No speech script, skipping TTS")
            return {**state, "tts_audio_path": None}
        
        elevenlabs = get_elevenlabs_client()
        
        audio_path = await elevenlabs.synthesize_speech(speech_script)
        
        if audio_path:
            logging.info(f"TTS audio saved: {audio_path}")
            return {**state, "tts_audio_path": audio_path}
        else:
            return {**state, "tts_audio_path": None}
    
    except Exception as e:
        logging.error(f"TTSAgent error: {e}")
        return state


async def InitialAudioRendererTool(state: DJState) -> DJState:
    """Render initial song with TTS intro prepended."""
    logging.info("InitialAudioRendererTool: Rendering initial song with intro TTS")
    
    try:
        song_b_path = state.get("song_b_path")
        tts_path = state.get("tts_audio_path")
        
        if not song_b_path or not os.path.exists(song_b_path):
            logging.warning("No valid song path for initial render")
            return state
        
        # Ensure output directory exists
        os.makedirs(SEGMENT_DIR, exist_ok=True)
        
        # Create output path
        import uuid
        mix_id = uuid.uuid4().hex[:8]
        output_path = os.path.join(SEGMENT_DIR, f"intro_{mix_id}.mp3")
        
        if tts_path and os.path.exists(tts_path):
            # Prepend TTS to the beginning of the song using ffmpeg
            # IMPORTANT: Trim song to end BEFORE the transition point so next segment can handle transition
            import subprocess
            
            # Get TTS duration
            try:
                probe_cmd = [
                    'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                    '-of', 'default=noprint_wrappers=1:nokey=1', tts_path
                ]
                result = subprocess.run(probe_cmd, capture_output=True, text=True)
                tts_duration = float(result.stdout.strip()) if result.stdout.strip() else 3.0
            except:
                tts_duration = 3.0
            
            # Get song duration
            try:
                probe_cmd = [
                    'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                    '-of', 'default=noprint_wrappers=1:nokey=1', song_b_path
                ]
                result = subprocess.run(probe_cmd, capture_output=True, text=True)
                song_duration = float(result.stdout.strip()) if result.stdout.strip() else 210.0
            except:
                song_duration = 210.0
            
            # Trim song to end ~20 seconds before the end
            # The next segment (mix) starts exactly at (duration - 20)
            transition_buffer = 20.0  # Match song1_lead_in in dj_mix.py
            song_trim_duration = song_duration - transition_buffer
            if song_trim_duration < 60:  # Minimum 60 seconds of song
                song_trim_duration = song_duration - 15  # Leave at least 15s for transition
            
            logging.info(f"TTS duration: {tts_duration}s, Song duration: {song_duration}s, Trimming to: {song_trim_duration}s")
            
            # Strategy: TTS plays fully, then song starts with overlap, song is TRIMMED
            # NO fade-out at the end - the transition segment will handle the crossfade
            fade_out_duration = 0.5
            overlap_duration = 1.0
            
            song_delay_ms = int((tts_duration - overlap_duration) * 1000)
            if song_delay_ms < 0:
                song_delay_ms = 0
            
            # Filter with song trimming (no fade-out - next segment handles transition)
            filter_complex = (
                f"[0:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo,"
                f"afade=t=out:st={tts_duration - fade_out_duration}:d={fade_out_duration}[tts];"
                f"[1:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo,"
                f"atrim=start=0:duration={song_trim_duration},asetpts=PTS-STARTPTS,"
                f"adelay={song_delay_ms}|{song_delay_ms},"
                f"afade=t=in:st=0:d={overlap_duration}[song];"
                f"[tts][song]amix=inputs=2:duration=longest:dropout_transition=0[out]"
            )
            
            cmd = [
                'ffmpeg', '-y',
                '-i', tts_path,
                '-i', song_b_path,
                '-filter_complex', filter_complex,
                '-map', '[out]',
                '-acodec', 'libmp3lame', '-b:a', '320k',
                output_path
            ]
            
            logging.info(f"Running ffmpeg for intro mix (TTS: {tts_duration}s, song trimmed to: {song_trim_duration}s)")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logging.error(f"FFmpeg error: {result.stderr}")
                # Fallback: just concatenate without fancy mixing
                logging.info("Trying simple concat fallback...")
                concat_cmd = [
                    'ffmpeg', '-y',
                    '-i', tts_path,
                    '-i', song_b_path,
                    '-filter_complex', '[0:a][1:a]concat=n=2:v=0:a=1[out]',
                    '-map', '[out]',
                    '-acodec', 'libmp3lame', '-b:a', '192k',
                    output_path
                ]
                result = subprocess.run(concat_cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    logging.error(f"Concat fallback also failed: {result.stderr}")
                    import shutil
                    shutil.copy(song_b_path, output_path)
        else:
            # No TTS, just copy song
            logging.info("No TTS available, using song directly")
            import shutil
            shutil.copy(song_b_path, output_path)
        
        # Verify output
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            if file_size > 0:
                logging.info(f"Rendered initial segment: {output_path} ({file_size} bytes)")
                return {**state, "rendered_segment_path": output_path}
        
        logging.error(f"Initial render failed: {output_path}")
        return state
    
    except Exception as e:
        logging.error(f"InitialAudioRendererTool error: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return state


async def AudioRendererTool(state: DJState) -> DJState:
    """Render audio mix using ffmpeg-python DJ mix engine."""
    logging.info("AudioRendererTool: Rendering mix with DJ mix engine")
    
    try:
        transition_plan = state.get("transition_plan")
        if not transition_plan:
            logging.warning("No transition plan, skipping render")
            return state
        
        # Get song file paths
        song_a_path = state.get("song_a_path")
        song_b_path = state.get("song_b_path")
        
        if not song_b_path or not os.path.exists(song_b_path):
            logging.warning("No valid song B path, cannot render")
            return state
        
        # Get TTS path if available
        tts_path = state.get("tts_audio_path")
        if tts_path and not os.path.exists(tts_path):
            tts_path = None
        
        # Ensure output directory exists
        os.makedirs(SEGMENT_DIR, exist_ok=True)
        
        # Create output path
        import uuid
        mix_id = uuid.uuid4().hex[:8]
        output_path = os.path.join(SEGMENT_DIR, f"mix_{mix_id}.mp3")
        
        # Extract plan parameters
        transition_type = transition_plan.get('transition_type', 'blend')
        t_start = transition_plan.get('transition_start')
        xfade_dur = transition_plan.get('crossfade_duration', 10.0)
        tts_offset = transition_plan.get('tts_start_offset', 5.0)
        
        # Check if we have song A for transition
        has_song_a = song_a_path and os.path.exists(song_a_path)
        
        if has_song_a:
            # Full transition between two songs
            result_path = create_dj_mix(
                song1_path=song_a_path,
                song2_path=song_b_path,
                transition_type=transition_type,
                output_path=output_path,
                t_start=t_start,
                xfade_dur=xfade_dur,
                tts_offset=tts_offset,
                tts_path=tts_path
            )
        else:
            # First song - just play song B (no transition needed)
            logging.info("No song A - copying song B as output")
            import shutil
            shutil.copy(song_b_path, output_path)
            result_path = output_path
        
        if not result_path:
            logging.error(f"DJ mix rendering failed for {output_path}")
            return state
        
        # Verify output file exists and has content
        if not os.path.exists(result_path):
            logging.error(f"Output file not created: {result_path}")
            return state
        
        file_size = os.path.getsize(result_path)
        if file_size == 0:
            logging.error(f"Output file is empty: {result_path}")
            return state
        
        logging.info(f"Rendered mix: {result_path} ({file_size} bytes)")
        return {**state, "rendered_segment_path": result_path}
    
    except Exception as e:
        logging.error(f"AudioRendererTool error: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return state


async def PersistenceNode(state: DJState) -> DJState:
    """Persist segment and play history to database."""
    logging.info("PersistenceNode: Saving to database")
    
    try:
        db = await get_db()
        session_id = state.get("session_id", "")
        selected_uuid = state.get("selected_song_uuid")
        rendered_path = state.get("rendered_segment_path")
        
        if rendered_path and selected_uuid:
            # Insert segment record
            segment_data = {
                'session_id': session_id,
                'segment_index': 0,  # TODO: track actual index
                'song_uuid': selected_uuid,
                'file_path_transport': rendered_path,
                'duration_sec': 30,
                'transition_id': None,
                'tts_used': 1 if state.get("tts_audio_path") else 0
            }
            
            segment_id = await db.insert_segment(segment_data)
            logging.info(f"Saved segment {segment_id}")
            
            # Update play count
            await db.update_play_count(selected_uuid)
            
            # Record play history so planning agent can find previous song
            from datetime import datetime
            await db.insert_play_history({
                'session_id': session_id,
                'song_uuid': selected_uuid,
                'started_at': datetime.utcnow().isoformat(),
                'transition_type': 'planned'
            })
        
        return state
    
    except Exception as e:
        logging.error(f"PersistenceNode error: {e}")
        return state


async def EmitEventsNode(state: DJState) -> DJState:
    """Emit WebSocket events to frontend."""
    logging.info("EmitEventsNode: Broadcasting events")
    
    try:
        from backend.orchestration.events import get_event_emitter
        
        emitter = get_event_emitter()
        
        selected_uuid = state.get("selected_song_uuid")
        if selected_uuid:
            await emitter.emit("now_playing", {
                "song_uuid": selected_uuid,
                "status": "playing"
            })
        
        decision_trace = state.get("decision_trace", [])
        if decision_trace:
            await emitter.emit("decision_trace", {
                "trace": decision_trace[-5:]  # Last 5 decisions
            })
        
        # Emit segment_ready if rendered with URL
        rendered_path = state.get("rendered_segment_path")
        if rendered_path:
            import os
            segment_filename = os.path.basename(rendered_path)
            segment_url = f"/audio/segments/{segment_filename}"
            logging.info(f"EmitEventsNode: Emitting segment_ready event: {segment_url}")
            await emitter.emit("segment_ready", {
                "segment_url": segment_url,
                "segment_path": rendered_path,
                "song_uuid": selected_uuid
            })
            logging.info(f"EmitEventsNode: Segment event emitted successfully")
        else:
            logging.warning("EmitEventsNode: No rendered_segment_path to emit")
        
        return state
    
    except Exception as e:
        logging.error(f"EmitEventsNode error: {e}")
        return state


def create_initialization_graph() -> object:
    """Create initialization graph for initial song selection, download, and intro TTS."""
    if StateGraph is None:
        logging.warning("LangGraph not installed, skipping initialization graph setup.")
        return None
    
    try:
        builder = StateGraph(DJState)
        
        # Add nodes for initialization with intro TTS
        builder.add_node("initial_song_selector", InitialSongSelectorAgent)
        builder.add_node("download_song", DownloadSongTool)
        builder.add_node("save_metadata", SaveMetadataNode)
        builder.add_node("initial_speech_writer", InitialSpeechWriterAgent)
        builder.add_node("tts", TTSAgent)
        builder.add_node("initial_audio_renderer", InitialAudioRendererTool)
        builder.add_node("persistence", PersistenceNode)
        builder.add_node("emit_events", EmitEventsNode)
        
        # Wire the flow: select -> download -> metadata -> speech -> TTS -> render -> persist -> emit
        builder.add_edge(START, "initial_song_selector")
        builder.add_edge("initial_song_selector", "download_song")
        builder.add_edge("download_song", "save_metadata")
        builder.add_edge("save_metadata", "initial_speech_writer")
        builder.add_edge("initial_speech_writer", "tts")
        builder.add_edge("tts", "initial_audio_renderer")
        builder.add_edge("initial_audio_renderer", "persistence")
        builder.add_edge("persistence", "emit_events")
        builder.add_edge("emit_events", END)
        
        graph = builder.compile()
        logging.info("Initialization graph compiled successfully")
        return graph
    
    except Exception as e:
        logging.warning(f"Failed to compile initialization graph: {e}")
        return None


def create_planning_graph() -> object:
    """Create planning graph that runs during playback."""
    if StateGraph is None:
        logging.warning("LangGraph not installed, skipping planning graph setup.")
        return None
    
    try:
        builder = StateGraph(DJState)
        
        # Add all nodes
        builder.add_node("planning_agent", PlanningAgent)
        builder.add_node("check_cache", CheckCacheTool)
        builder.add_node("download_if_needed", DownloadIfNeededTool)
        builder.add_node("parallel_planning", ParallelPlanningNode)  # Concurrent transition + speech
        builder.add_node("tts", TTSAgent)
        builder.add_node("audio_renderer", AudioRendererTool)
        builder.add_node("persistence", PersistenceNode)
        builder.add_node("emit_events", EmitEventsNode)
        
        # Wire the graph flow
        builder.add_edge(START, "planning_agent")
        builder.add_edge("planning_agent", "check_cache")
        builder.add_edge("check_cache", "download_if_needed")
        builder.add_edge("download_if_needed", "parallel_planning")  # Run transition + speech concurrently
        builder.add_edge("parallel_planning", "tts")
        builder.add_edge("tts", "audio_renderer")
        builder.add_edge("audio_renderer", "persistence")
        builder.add_edge("persistence", "emit_events")
        builder.add_edge("emit_events", END)
        
        graph = builder.compile()
        logging.info("Planning graph compiled successfully")
        return graph
    
    except Exception as e:
        logging.warning(f"Failed to compile planning graph: {e}")
        return None


def create_dj_planning_graph() -> object:
    """Legacy function - returns planning graph for backward compatibility."""
    return create_planning_graph()
