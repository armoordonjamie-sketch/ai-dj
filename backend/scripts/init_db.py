import os
import sqlite3
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Database configuration
DB_PATH = os.getenv('DB_PATH', 'data/persistence.db')

# Initialize the database
def init_db():
    # Convert to Path object for cross-platform compatibility
    db_path = Path(DB_PATH)
    
    # Ensure parent directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Check if DB_PATH points to a directory instead of a file
    if db_path.exists() and db_path.is_dir():
        raise ValueError(f"DB_PATH points to a directory; expected file. Remove {db_path} directory.")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create tables
    cursor.execute('''CREATE TABLE IF NOT EXISTS songs (
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

    cursor.execute('''CREATE TABLE IF NOT EXISTS song_features (
        song_uuid TEXT,
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

    cursor.execute('''CREATE TABLE IF NOT EXISTS lyrics_analysis (
        song_uuid TEXT,
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

    cursor.execute('''CREATE TABLE IF NOT EXISTS popularity_daily (
        song_uuid TEXT,
        platform TEXT,
        date TEXT,
        popularity_value REAL,
        FOREIGN KEY (song_uuid) REFERENCES songs (uuid)
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        started_at TEXT,
        ended_at TEXT,
        mode TEXT,
        user_context_snapshot TEXT
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS play_history (
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

    cursor.execute('''CREATE TABLE IF NOT EXISTS segments (
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

    cursor.execute('''CREATE TABLE IF NOT EXISTS llm_trace (
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

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print('Database initialized successfully.')
