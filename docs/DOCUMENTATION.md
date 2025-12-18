# AI DJ (Gemini on OpenRouter + LangGraph) — System Documentation

> **Goal:** a personal “AI DJ” that plays music continuously in a desktop browser via **WebRTC audio**, while multiple async AI agents plan tracks, transitions (as **FFmpeg filtergraphs**), and occasional humorous “DJ talk” via **ElevenLabs TTS**.

---

## Tech stack

- **Backend:** Python + **FastAPI** (HTTP + WebSocket + WebRTC signaling) citeturn1search0  
- **Orchestration:** **LangGraph** (async graph + streaming updates) citeturn0search0turn0search20  
- **LLM:** **Gemini 2.5 Flash** on **OpenRouter**, with controllable reasoning/thinking budget citeturn0search1turn0search9  
- **Metadata / lyrics / popularity:** **Soundcharts API** citeturn2search0turn0search3turn2search1  
- **TTS:** ElevenLabs **Eleven Flash v2.5**, voice id `st7NwhTPEzqo2riw7qWC` citeturn0search6turn0search10  
- **Audio rendering:** **ffmpeg filtergraph** strings produced by the Transition agent citeturn1search2  
- **WebRTC:** Python backend using **aiortc** (asyncio-based) citeturn1search1  
- **DB:** SQLite (songs, plays, segments, prompts, cache mgmt)
- **Frontend:** Vite + TypeScript + Tailwind + Framer Motion (WebRTC receive + WebSocket UI events)

---

## Core ideas

### 1) Segment-based generation, WebRTC delivery
- The system renders **~30s audio segments** ahead of playback and stores each segment for replay/debug (metadata in SQLite + audio file on disk).
- The browser receives audio as a **WebRTC audio track** (Opus is the typical transport codec), while the UI gets structured state/events over a **WebSocket**.

### 2) Multi-agent async planning with LangGraph
Agents run concurrently (async nodes + `asyncio.gather`) to keep “DJ” smooth:
- Plan **1–2 songs ahead** (and several segments ahead) to hide model + ffmpeg + TTS latency.
- Stream intermediate “why / what’s next / DJ says…” events to the UI using LangGraph streaming. citeturn0search0turn0search20

### 3) Transition Agent outputs FFmpeg filtergraphs (guarded)
Your Transition agent returns an `ffmpeg -filter_complex` recipe. Filtergraphs are validated against a whitelist and hard limits before execution, using FFmpeg’s filtergraph syntax rules. citeturn1search2

The transition “vocabulary” and decision framework comes from your transition field guide (blend/bass swap/cut/echo-out/reverb-out/loop tricks/wordplay/etc.). fileciteturn1file1turn1file2turn1file6

---

## User modes and “station context”

### Modes
- **Autonomous:** DJ drives track selection and style changes itself.
- **Guided:** user influence via:
  - mood slider (valence/energy targets)
  - genre picks
  - “more like this”
  - skip
  - freeform prompt: e.g. “I’m in the mood for songs from the 2010s”

### Context and personalization
- A **user context file** (per user; currently just you) is included in prompts, e.g.:
  - “Aaron is secretly a Swiftie”
- DJ can use this to do personalized shoutouts and jokes.
- A self-hosted **Firecrawl MCP** server is available for factual lookups, so the DJ can reference real facts when desired. citeturn1search3turn1search7turn1search11

---

## External data sources

### Soundcharts API usage (load-bearing endpoints)
You’ll store the Soundcharts **song UUID** as the primary identifier in your DB.

- **Search song by name**: typo-tolerant query to resolve song UUID citeturn2search3  
- **Get song metadata**: audio features like danceability/energy/tempo/key/mode/valence/etc. citeturn2search0  
- **Get lyrics analysis**: themes/moods/references/locations/narrative style + 1–10 scoring metrics citeturn0search3turn0search15  
- **Get popularity**: platform popularity (Spotify/Tidal/Deezer) citeturn2search1  
- **Getting started / base URL**: Soundcharts API environment info citeturn2search14  

---

## System architecture

### Process layout
Single server, single “station session” (personal use):

- **FastAPI app**
  - `/ws` WebSocket for UI state/events
  - `/webrtc/offer` HTTP endpoint for WebRTC SDP offer/answer
  - `/control/*` HTTP endpoints (or WS messages) for user controls

- **DJ Engine**
  - one active Session
  - a background async task maintains:
    - `segment_queue` (ready-to-play)
    - `planning_queue` (planned upcoming songs + transitions)
  - a WebRTC AudioTrack pulls PCM frames from `segment_queue` and streams them

- **SQLite + disk storage**
  - SQLite stores *metadata* about songs, plays, decisions, prompts, segments
  - Disk stores *audio*:
    - cached songs (up to 50GB, least-played eviction)
    - rendered segments (stored for replay/debug)

### High-level flow
1. Frontend loads → opens WebSocket → initiates WebRTC offer → receives audio track.
2. DJ Engine ensures N segments are ready:
   - if low, it triggers planning + rendering in parallel
3. As segments are created:
   - enqueue for playback
   - emit UI events (`now_playing`, `dj_says`, `up_next`, `decision_trace`, etc.)
4. User actions (skip / mood / prompt) update Session state and influence planning immediately.

---

## LangGraph orchestration

### State (suggested)
Use a typed state object (dataclass / TypedDict) that’s serializable and easy to snapshot:

- `session_id: str`
- `mode: "autonomous" | "guided"`
- `user_controls: { mood: float, genre_whitelist: [...], prompt: str | None, more_like_song_uuid: str | None }`
- `now_playing: { song_uuid, title, artist, position_sec }`
- `history: list[PlayEvent]` (song_uuid, played_at, skip?, transition_type, etc.)
- `library: { cached_song_uuids, cache_bytes_used }`
- `plan: { next_songs: [...], next_transitions: [...], next_speech: [...] }`
- `segment_cursor: { song_uuid, song_offset_sec, segment_index }`
- `debug: { last_prompts, last_tool_calls, last_errors }`

### Graph nodes (agents/tools)
1. **ControlIngestNode**
   - reads user control changes from WS and updates state

2. **TrackSelectorAgent**
   - uses Soundcharts metadata/popularity/lyrics + history to pick next song UUID
   - respects user controls (prompt, genre, mood)

3. **TransitionPlannerAgent**
   - reads A→B relationship (tempo/key/energy/vocals/lyrics)
   - chooses a transition strategy using your field guide fileciteturn1file6turn1file2
   - outputs **FFmpeg filtergraph recipe** (see “Transition contract”)

4. **SpeechWriterAgent**
   - decides “talk sometimes”:
     - primarily when changing style/artist/energy/era
   - writes humorous DJ script (can use Firecrawl MCP for facts) citeturn1search3turn1search11
   - incorporates user context file

5. **TTSAgent**
   - calls ElevenLabs TTS using your voice ID + Eleven Flash v2.5 citeturn0search6turn0search10
   - returns an audio file (WAV/MP3) to be mixed

6. **AudioRendererTool**
   - runs `ffmpeg` with the TransitionPlanner’s `filter_complex`
   - produces a 30s segment (archive + transport formats)

7. **PersistenceNode**
   - writes plays/segments/prompts/decisions to SQLite

8. **EmitEventsNode**
   - pushes UI events to WS (and optionally uses LangGraph streaming updates) citeturn0search0turn0search20

---

## Model configuration (Gemini 2.5 Flash via OpenRouter)

### Reasoning/thinking budgets
Gemini 2.5 introduces a **thinking budget** control. citeturn0search9turn0search1  
Use it to keep “fast” nodes cheap and “creative/planning” nodes deeper:

- TrackSelectorAgent: medium budget
- TransitionPlannerAgent: low→medium (more deterministic; avoid rambling)
- SpeechWriterAgent: medium→high (comedy + facts + personalization)
- Tool / renderer nodes: no LLM

On OpenRouter, Gemini 2.5 Flash supports “max tokens for reasoning” style configuration. citeturn0search1turn0search17

---

## Transition Agent contract

### Why a contract?
Because the agent outputs an executable filtergraph, you need a strict schema + validation.

FFmpeg filtergraphs are text-based graphs supplied to `-filter_complex`. citeturn1search2

### Output schema (JSON)
```json
{
  "transition_id": "uuid",
  "transition_type": "echo_out_slam",
  "rationale": "Keys clash, tempo far apart, hard reset needed.",
  "inputs": {
    "A": {"path": "cache/songs/A.wav", "start": 120.0},
    "B": {"path": "cache/songs/B.wav", "start": 45.0},
    "TTS": {"path": "cache/tts/seg42.wav", "start": 2.0}
  },
  "segment": {"duration": 30.0, "sample_rate": 48000},
  "ffmpeg": {
    "filter_complex": "[0:a]atrim=start=120:duration=30,asetpts=PTS-STARTPTS[a];[1:a]atrim=start=45:duration=30,asetpts=PTS-STARTPTS[b];[a][b]acrossfade=d=1.5[c];[2:a]atrim=start=0:duration=6,asetpts=PTS-STARTPTS[tts];[c][tts]sidechaincompress=threshold=0.05:ratio=8[ducked]",
    "map": "[ducked]"
  },
  "safety": {
    "uses_only_whitelisted_filters": true,
    "max_filtergraph_length": 2000
  }
}
```

### Validation rules (recommended)
- Only allow a whitelist of audio filters (e.g. `atrim`, `asetpts`, `acrossfade`, `afade`, `aecho`, `highpass`, `lowpass`, `equalizer`, `acompressor/sidechaincompress`, `alimiter`, `adelay`, `volume`, `pan`, `aresample`).
- Cap:
  - filtergraph length
  - number of filters
  - max delay/feedback values
- Reject shell metacharacters; pass args to `subprocess` as a list (no shell).

### Transition strategy guidance (from your field guide)
The agent should reason in terms of:
- time/phrase alignment
- frequency management (bass ownership / EQ swaps)
- harmony (key clash risk)
- energy (up/down)
- attention (vocal collision / FX distraction)

These “families” map directly to filtergraph patterns: straight blend, bass swap, filter blend, slam cut, echo-out, reverb-out, loop roll/loop mix, wordplay/lyric handoffs, brake/spinback-style resets. fileciteturn1file1turn1file2turn1file9turn1file5

---

## Audio pipeline

### Audio formats
- **Internal working format:** 48 kHz PCM (WAV) for predictable mixing.
- **Transport format (WebRTC):** Opus via WebRTC audio track (browser-native).
- **Archive format for debug:** store the final rendered segment as Opus/MP3 *and* optionally a WAV/FLAC (configurable).

### Rendering steps per segment
1. Resolve song UUIDs → ensure both A and B audio are locally available (cache).
2. Convert source files to normalized working WAV:
   - consistent sample rate (48k), channel layout, loudness target.
3. If DJ talk is needed:
   - write script
   - synthesize with ElevenLabs (Flash v2.5) citeturn0search6turn0search10
4. Call ffmpeg:
   - use agent filtergraph to produce a **30s segment**
   - store segment + metadata row

---

## WebRTC delivery (desktop browser)

### Backend
- Use `aiortc` to create a `RTCPeerConnection` and add an `AudioStreamTrack` that consumes PCM frames from the segment queue. `aiortc` is asyncio-based, aligning with your async design. citeturn1search1

### Signaling (simple, server-driven)
- `POST /webrtc/offer` with `{ sdp, type }`
- server returns `{ sdp, type: "answer" }`
- ICE candidates can be “trickle” via WebSocket or bundled, depending on frontend choice.

### Frontend
- Create `RTCPeerConnection`
- Send offer to `/webrtc/offer`
- Set remote description (answer)
- On `pc.ontrack`, attach stream to an `<audio autoplay />` element.

---

## WebSocket UI events

FastAPI’s WebSocket support is used for structured events + controls. citeturn1search0

### Server → client events (examples)
```ts
type DjEvent =
  | { type: "now_playing"; song: SongView; segmentIndex: number; startedAt: string }
  | { type: "up_next"; songs: SongView[] }
  | { type: "dj_says"; text: string; ttsSegmentId: string | null }
  | { type: "decision_trace"; why: string; featuresUsed: string[] }
  | { type: "cache_status"; usedBytes: number; limitBytes: number }
  | { type: "error"; message: string; recoverable: boolean };
```

### Client → server controls (examples)
```ts
type DjControl =
  | { type: "set_mode"; mode: "autonomous" | "guided" }
  | { type: "set_mood"; mood: number } // 0..1
  | { type: "set_genres"; genres: string[] }
  | { type: "prompt"; text: string }
  | { type: "skip" }
  | { type: "more_like_this"; songUuid: string };
```

---

## SQLite data model (suggested tables)

### `songs`
- `uuid` (Soundcharts UUID, PK)
- `title`, `artist`, `release_date`, `language_code`, `explicit`
- `local_path`, `duration_sec`, `filesize_bytes`
- `play_count`, `last_played_at`

### `song_features`
- `song_uuid` (FK)
- `acousticness`, `danceability`, `energy`, `instrumentalness`, `key`, `mode`,
  `liveness`, `loudness`, `speechiness`, `tempo`, `time_signature`, `valence`
(derived from Soundcharts “Get song metadata”) citeturn2search0

### `lyrics_analysis`
- `song_uuid` (FK)
- `themes`, `moods`, `brands`, `locations`, `cultural_ref_people`, `cultural_ref_non_people`
- `narrative_style`
- `emotional_intensity_score`, `imagery_score`, `complexity_score`, `rhyme_scheme_score`, `repetitiveness_score`
(from Soundcharts lyrics analysis) citeturn0search3turn0search15

### `popularity_daily`
- `song_uuid` (FK)
- `platform` (`spotify|tidal|deezer`)
- `date`, `popularity_value`
(from Soundcharts popularity endpoint) citeturn2search1

### `sessions`
- `session_id` (PK)
- `started_at`, `ended_at`
- `mode`, `user_context_snapshot`

### `play_history`
- `id` (PK)
- `session_id`, `song_uuid`
- `started_at`, `ended_at`, `skipped`
- `transition_type`, `transition_id`

### `segments`
- `id` (PK)
- `session_id`
- `segment_index`
- `song_uuid` (current “dominant” song or mix anchor)
- `file_path_transport` (e.g., `.opus`/`.mp3`)
- `file_path_archive` (optional `.wav`/`.flac`)
- `duration_sec`
- `transition_id`
- `tts_used` (bool)
- `created_at`

### `llm_trace`
- `id` (PK)
- `session_id`
- `agent_name`
- `prompt`, `response`
- `model`, `thinking_budget`
- `created_at`

### Cache eviction rule (50GB, least-played)
- Maintain `songs.filesize_bytes` + `songs.play_count` and evict in ascending `(play_count, last_played_at)` until under limit.

---

## Ingestion & caching notes

- You maintain a local cache directory managed by the server (50GB limit, least-played eviction).
- Any acquisition/downloading logic must respect your licensing/rights and local laws. (Implementation is intentionally not documented as a step-by-step “ripping” guide.)

---

## Error handling and resilience

### Common failure points
- Soundcharts API outages / rate limits
- LLM latency spikes
- ElevenLabs TTS failures
- ffmpeg render errors
- cache misses (song not yet locally available)

### Recovery strategy
- Keep a minimum “ready” buffer of segments (e.g., 4–8).
- If a render fails:
  - fall back to a simpler transition recipe (agent retry with “safe blend”)
  - or play a short “filler” segment (previous loop / ambient bed) while recovering
- Always emit an `error` WS event for UI visibility.

---

## Frontend (Vite + TS + Tailwind + Framer Motion)

### UI panels (minimum viable)
- **Now playing**: title, artist, album art (if available)
- **DJ says**: current spoken line + transcript
- **Up next**: next 1–3 tracks
- **Controls**:
  - mode toggle
  - mood slider
  - genre chips
  - prompt input
  - skip button

### Data flow
- WebRTC: audio playback only
- WebSocket: all UI state + controls

---

## Configuration

Recommended `config.yaml` keys:
- `openrouter.api_key`
- `openrouter.model = "google/gemini-2.5-flash"`
- `openrouter.max_reasoning_tokens.{agent}`
- `soundcharts.app_id`, `soundcharts.api_key`, `soundcharts.base_url`
- `elevenlabs.api_key`, `elevenlabs.voice_id`, `elevenlabs.model_id="eleven_flash_v2_5"`
- `paths.song_cache_dir`, `paths.segment_dir`, `paths.user_context_file`
- `cache.max_bytes = 50_000_000_000`
- `audio.segment_seconds = 30`, `audio.sample_rate = 48000`
- `ffmpeg.path = "ffmpeg"`, `ffmpeg.filter_whitelist=[...]`
- `webrtc.ice_servers=[...]`

---

## Appendices

### A) Transition field guide (authoritative)
Use the transition families, decision framework, and “recipes” in your provided guide as the agent’s mental model. fileciteturn1file6turn1file7turn1file9

### B) References
- LangGraph streaming (`stream` / `astream`, stream modes like `"updates"`) citeturn0search0turn0search20  
- FFmpeg filtergraph syntax (`-filter_complex`) citeturn1search2  
- FastAPI WebSockets citeturn1search0  
- aiortc (asyncio-based WebRTC for Python) citeturn1search1  
- Soundcharts song metadata / lyrics analysis / popularity / search citeturn2search0turn0search3turn2search1turn2search3  
- ElevenLabs TTS convert endpoint + Flash v2.5 model citeturn0search10turn0search6  
- Gemini thinking budget parameter (Gemini 2.5) citeturn0search9  
- Firecrawl MCP server (self-hosted) citeturn1search3turn1search7turn1search11  
