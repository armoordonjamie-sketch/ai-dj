"""Database operations for AI DJ persistence layer."""
import aiosqlite
import os
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path
from backend.config import DB_PATH, CACHE_MAX_BYTES, SONG_CACHE_DIR


class Database:
    """Async SQLite database manager for AI DJ."""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None
    
    async def connect(self):
        """Establish database connection and ensure tables exist."""
        # Ensure parent directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        
        # Auto-create tables if they don't exist
        await self._create_tables()
    
    async def _create_tables(self):
        """Create all required database tables if they don't exist."""
        await self._conn.execute('''CREATE TABLE IF NOT EXISTS songs (
            uuid TEXT PRIMARY KEY,
            title TEXT,
            artist TEXT,
            release_date TEXT,
            language_code TEXT,
            explicit INTEGER,
            local_path TEXT,
            duration_sec REAL,
            filesize_bytes INTEGER,
            play_count INTEGER DEFAULT 0,
            last_played_at TEXT
        )''')
        
        await self._conn.execute('''CREATE TABLE IF NOT EXISTS song_features (
            song_uuid TEXT PRIMARY KEY,
            acousticness REAL,
            danceability REAL,
            energy REAL,
            instrumentalness REAL,
            key INTEGER,
            mode INTEGER,
            liveness REAL,
            loudness REAL,
            speechiness REAL,
            tempo REAL,
            time_signature INTEGER,
            valence REAL,
            FOREIGN KEY (song_uuid) REFERENCES songs (uuid)
        )''')
        
        await self._conn.execute('''CREATE TABLE IF NOT EXISTS lyrics_analysis (
            song_uuid TEXT PRIMARY KEY,
            themes TEXT,
            moods TEXT,
            brands TEXT,
            locations TEXT,
            cultural_ref_people TEXT,
            cultural_ref_non_people TEXT,
            narrative_style TEXT,
            emotional_intensity_score REAL,
            imagery_score REAL,
            complexity_score REAL,
            rhyme_scheme_score REAL,
            repetitiveness_score REAL,
            FOREIGN KEY (song_uuid) REFERENCES songs (uuid)
        )''')
        
        await self._conn.execute('''CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            started_at TEXT,
            ended_at TEXT,
            mode TEXT,
            user_context_snapshot TEXT
        )''')
        
        await self._conn.execute('''CREATE TABLE IF NOT EXISTS play_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            song_uuid TEXT,
            started_at TEXT,
            ended_at TEXT,
            skipped INTEGER,
            transition_type TEXT,
            transition_id TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions (session_id),
            FOREIGN KEY (song_uuid) REFERENCES songs (uuid)
        )''')
        
        await self._conn.execute('''CREATE TABLE IF NOT EXISTS segments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            segment_index INTEGER,
            song_uuid TEXT,
            file_path_transport TEXT,
            file_path_archive TEXT,
            duration_sec REAL,
            transition_id TEXT,
            tts_used INTEGER,
            created_at TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions (session_id),
            FOREIGN KEY (song_uuid) REFERENCES songs (uuid)
        )''')
        
        await self._conn.execute('''CREATE TABLE IF NOT EXISTS llm_trace (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            agent_name TEXT,
            prompt TEXT,
            response TEXT,
            model TEXT,
            thinking_budget REAL,
            created_at TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions (session_id)
        )''')
        
        await self._conn.commit()
    
    async def close(self):
        """Close database connection."""
        if self._conn:
            await self._conn.close()
    
    # Song operations
    async def get_song(self, uuid: str) -> Optional[Dict[str, Any]]:
        """Get song by UUID."""
        async with self._conn.execute(
            "SELECT * FROM songs WHERE uuid = ?", (uuid,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def insert_song(self, song_data: Dict[str, Any]) -> None:
        """Insert or update song record."""
        await self._conn.execute("""
            INSERT OR REPLACE INTO songs 
            (uuid, title, artist, release_date, language_code, explicit, 
             local_path, duration_sec, filesize_bytes, play_count, last_played_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            song_data['uuid'], song_data.get('title'), song_data.get('artist'),
            song_data.get('release_date'), song_data.get('language_code'),
            song_data.get('explicit', 0), song_data.get('local_path'),
            song_data.get('duration_sec'), song_data.get('filesize_bytes'),
            song_data.get('play_count', 0), song_data.get('last_played_at')
        ))
        await self._conn.commit()
    
    async def update_play_count(self, uuid: str) -> None:
        """Increment play count and update last played timestamp."""
        now = datetime.utcnow().isoformat()
        await self._conn.execute("""
            UPDATE songs 
            SET play_count = play_count + 1, last_played_at = ?
            WHERE uuid = ?
        """, (now, uuid))
        await self._conn.commit()
    
    async def get_cached_songs(self, limit: int = 50, exclude_uuids: List[str] = None) -> List[Dict[str, Any]]:
        """Get songs that are cached locally (have local_path)."""
        exclude_uuids = exclude_uuids or []
        placeholders = ','.join(['?'] * len(exclude_uuids)) if exclude_uuids else ''
        exclude_clause = f"AND uuid NOT IN ({placeholders})" if exclude_uuids else ""
        
        query = f"""
            SELECT uuid, title, artist, release_date, language_code, explicit,
                   local_path, duration_sec, filesize_bytes, play_count, last_played_at
            FROM songs
            WHERE local_path IS NOT NULL AND local_path != ''
            {exclude_clause}
            ORDER BY play_count ASC, COALESCE(last_played_at, '') ASC
            LIMIT ?
        """
        
        params = list(exclude_uuids) + [limit] if exclude_uuids else [limit]
        
        async with self._conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    # Song features operations
    async def insert_song_features(self, uuid: str, features: Dict[str, Any]) -> None:
        """Insert song audio features."""
        await self._conn.execute("""
            INSERT OR REPLACE INTO song_features
            (song_uuid, acousticness, danceability, energy, instrumentalness,
             key, mode, liveness, loudness, speechiness, tempo, time_signature, valence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            uuid, features.get('acousticness'), features.get('danceability'),
            features.get('energy'), features.get('instrumentalness'),
            features.get('key'), features.get('mode'), features.get('liveness'),
            features.get('loudness'), features.get('speechiness'),
            features.get('tempo'), features.get('time_signature'), features.get('valence')
        ))
        await self._conn.commit()
    
    async def get_song_features(self, uuid: str) -> Optional[Dict[str, Any]]:
        """Get song audio features."""
        async with self._conn.execute(
            "SELECT * FROM song_features WHERE song_uuid = ?", (uuid,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    # Lyrics analysis operations
    async def insert_lyrics_analysis(self, uuid: str, analysis: Dict[str, Any]) -> None:
        """Insert lyrics analysis data."""
        await self._conn.execute("""
            INSERT OR REPLACE INTO lyrics_analysis
            (song_uuid, themes, moods, brands, locations, cultural_ref_people,
             cultural_ref_non_people, narrative_style, emotional_intensity_score,
             imagery_score, complexity_score, rhyme_scheme_score, repetitiveness_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            uuid, analysis.get('themes'), analysis.get('moods'),
            analysis.get('brands'), analysis.get('locations'),
            analysis.get('cultural_ref_people'), analysis.get('cultural_ref_non_people'),
            analysis.get('narrative_style'), analysis.get('emotional_intensity_score'),
            analysis.get('imagery_score'), analysis.get('complexity_score'),
            analysis.get('rhyme_scheme_score'), analysis.get('repetitiveness_score')
        ))
        await self._conn.commit()
    
    # Session operations
    async def create_session(self, session_id: str, mode: str = "autonomous") -> None:
        """Create a new DJ session."""
        now = datetime.utcnow().isoformat()
        await self._conn.execute("""
            INSERT INTO sessions (session_id, started_at, mode)
            VALUES (?, ?, ?)
        """, (session_id, now, mode))
        await self._conn.commit()
    
    async def end_session(self, session_id: str) -> None:
        """Mark session as ended."""
        now = datetime.utcnow().isoformat()
        await self._conn.execute("""
            UPDATE sessions SET ended_at = ? WHERE session_id = ?
        """, (now, session_id))
        await self._conn.commit()
    
    # Play history operations
    async def insert_play_history(self, history_data: Dict[str, Any]) -> None:
        """Insert play history record."""
        await self._conn.execute("""
            INSERT INTO play_history
            (session_id, song_uuid, started_at, ended_at, skipped, transition_type, transition_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            history_data['session_id'], history_data['song_uuid'],
            history_data.get('started_at'), history_data.get('ended_at'),
            history_data.get('skipped', 0), history_data.get('transition_type'),
            history_data.get('transition_id')
        ))
        await self._conn.commit()
    
    async def get_recent_plays(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent play history for a session."""
        async with self._conn.execute("""
            SELECT * FROM play_history 
            WHERE session_id = ? 
            ORDER BY started_at DESC 
            LIMIT ?
        """, (session_id, limit)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def get_global_recent_plays(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent play history across ALL sessions."""
        async with self._conn.execute("""
            SELECT * FROM play_history 
            ORDER BY started_at DESC 
            LIMIT ?
        """, (limit,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    # Segment operations
    async def insert_segment(self, segment_data: Dict[str, Any]) -> int:
        """Insert rendered segment record and return segment ID."""
        cursor = await self._conn.execute("""
            INSERT INTO segments
            (session_id, segment_index, song_uuid, file_path_transport,
             file_path_archive, duration_sec, transition_id, tts_used, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            segment_data['session_id'], segment_data.get('segment_index'),
            segment_data.get('song_uuid'), segment_data.get('file_path_transport'),
            segment_data.get('file_path_archive'), segment_data.get('duration_sec'),
            segment_data.get('transition_id'), segment_data.get('tts_used', 0),
            datetime.utcnow().isoformat()
        ))
        await self._conn.commit()
        return cursor.lastrowid
    
    # LLM trace operations
    async def insert_llm_trace(self, trace_data: Dict[str, Any]) -> None:
        """Insert LLM interaction trace."""
        await self._conn.execute("""
            INSERT INTO llm_trace
            (session_id, agent_name, prompt, response, model, thinking_budget, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            trace_data['session_id'], trace_data['agent_name'],
            trace_data.get('prompt'), trace_data.get('response'),
            trace_data.get('model'), trace_data.get('thinking_budget'),
            datetime.utcnow().isoformat()
        ))
        await self._conn.commit()
    
    # Cache management
    async def get_cache_size(self) -> int:
        """Get total size of cached songs in bytes."""
        async with self._conn.execute(
            "SELECT SUM(filesize_bytes) as total FROM songs WHERE local_path IS NOT NULL"
        ) as cursor:
            row = await cursor.fetchone()
            return row['total'] if row['total'] else 0
    
    async def evict_least_played_songs(self, target_bytes: int = CACHE_MAX_BYTES) -> List[str]:
        """Evict least-played songs until under target size. Returns list of evicted UUIDs."""
        current_size = await self.get_cache_size()
        if current_size <= target_bytes:
            return []
        
        evicted = []
        async with self._conn.execute("""
            SELECT uuid, local_path, filesize_bytes
            FROM songs
            WHERE local_path IS NOT NULL
            ORDER BY play_count ASC, last_played_at ASC
        """) as cursor:
            async for row in cursor:
                if current_size <= target_bytes:
                    break
                
                # Delete file
                if row['local_path'] and os.path.exists(row['local_path']):
                    try:
                        os.remove(row['local_path'])
                    except Exception as e:
                        print(f"Failed to delete {row['local_path']}: {e}")
                
                # Update database
                await self._conn.execute("""
                    UPDATE songs 
                    SET local_path = NULL, filesize_bytes = NULL
                    WHERE uuid = ?
                """, (row['uuid'],))
                
                current_size -= (row['filesize_bytes'] or 0)
                evicted.append(row['uuid'])
        
        await self._conn.commit()
        return evicted


# Global database instance
_db: Optional[Database] = None


async def get_db() -> Database:
    """Get or create global database instance."""
    global _db
    if _db is None:
        _db = Database()
        await _db.connect()
    return _db


async def close_db():
    """Close global database instance."""
    global _db
    if _db:
        await _db.close()
        _db = None

