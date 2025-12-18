# Persistence Layer Implementation Notes

## Database Schema

### Tables
1. **songs**
   - `uuid`: Soundcharts UUID, PK
   - `title`: Title of the song
   - `artist`: Artist of the song
   - `release_date`: Release date of the song
   - `language_code`: Language code of the song
   - `explicit`: Explicit content flag
   - `local_path`: Local file path of the song
   - `duration_sec`: Duration of the song in seconds
   - `filesize_bytes`: Size of the song file in bytes
   - `play_count`: Number of times the song has been played
   - `last_played_at`: Timestamp of the last play

2. **song_features**
   - `song_uuid`: Foreign key referencing songs
   - Acoustic features (danceability, energy, etc.)

3. **lyrics_analysis**
   - `song_uuid`: Foreign key referencing songs
   - Analysis metrics (themes, moods, etc.)

4. **popularity_daily**
   - `song_uuid`: Foreign key referencing songs
   - Popularity metrics per platform

5. **sessions**
   - `session_id`: Primary key for session tracking
   - Session metadata (started_at, ended_at, etc.)

6. **play_history**
   - `id`: Primary key for play history
   - Foreign keys for session and song

7. **segments**
   - `id`: Primary key for segments
   - Metadata for audio segments generated

8. **llm_trace**
   - `id`: Primary key for LLM trace
   - Metadata for LLM interactions

## Cache Management
- **Eviction Logic**: Maintain a 50GB limit on cached songs. Evict the least-played songs based on `play_count` and `last_played_at`.

## Segment Storage
- **Filesystem Layout**:
  - `/data/cache/songs`: Cached song files
  - `/data/segments`: Generated audio segments
  - `/data/tts`: Text-to-speech audio files

## Initialization Script
- A CLI script is provided in `/backend/scripts/init_db.py` to initialize the database and create the necessary tables.

### Windows Setup Instructions
1. Create the data directory (do NOT create the .db file):
   ```powershell
   mkdir data
   ```

2. Run the initialization script:
   ```powershell
   python backend/scripts/init_db.py
   ```

**Important Notes:**
- SQLite creates the database file (`persistence.db`) automatically - you don't need to create it manually
- If you accidentally created `data/persistence.db` as a directory (e.g., via `mkdir data/persistence.db`), you will get an error:
  ```
  ValueError: DB_PATH points to a directory; expected file. Remove <path> directory.
  ```
  To fix this, delete the directory:
  ```powershell
  rmdir data\persistence.db
  ```
  Then re-run the initialization script.

## Testing & Verification

### Tested Scenarios (Windows)
1. ✅ **Fresh initialization**: `mkdir data` → `python backend/scripts/init_db.py` works correctly
2. ✅ **Directory mistake detection**: If `data/persistence.db` is accidentally created as a directory, the script raises a clear error with remediation steps
3. ✅ **Parent directory auto-creation**: Script automatically creates the `data` directory if it doesn't exist

### Error Messages
If you accidentally create the database path as a directory:
```
ValueError: DB_PATH points to a directory; expected file. Remove data\persistence.db directory.
```

Fix by running:
```powershell
rmdir data\persistence.db
```

## Current Status
- The persistence layer has been successfully implemented, including the database schema, caching logic, and segment storage. The initialization script is ready for use.
- **Windows robustness verified**: Parent directory creation and directory detection work correctly on Windows 10.