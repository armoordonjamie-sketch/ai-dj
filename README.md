# AI DJ 🎧

> **An AI-powered personal DJ that creates seamless music mixes with intelligent transitions, personalized track selection, and humorous DJ commentary.**

![License](https://img.shields.io/badge/license-Private-red)
![Python](https://img.shields.io/badge/python-3.10+-blue)
![Node](https://img.shields.io/badge/node-18+-green)

## What It Does

AI DJ is a full-stack application that acts as your personal radio DJ. It:

- **Selects tracks** intelligently based on your preferences, mood, and listening history
- **Creates professional transitions** between songs using AI-analyzed audio (BPM, key, energy)
- **Generates DJ commentary** with personalized intros, jokes, and track announcements
- **Streams continuously** with gapless playback in your browser

## Tech Stack

| Component | Technology |
|-----------|------------|
| **Backend** | Python 3.10+ · FastAPI · LangGraph |
| **AI/LLM** | Gemini 2.0 Flash via OpenRouter (with audio analysis) |
| **Song Metadata** | Soundcharts API (features, popularity, lyrics) |
| **TTS** | ElevenLabs Flash v2.5 |
| **Audio Processing** | FFmpeg · ffmpeg-python |
| **Song Acquisition** | yt-dlp |
| **Database** | SQLite (aiosqlite) |
| **Frontend** | React · TypeScript · Vite · Tailwind · Framer Motion |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         BROWSER                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  React Frontend                                            │  │
│  │  • HTTP Audio Player (gapless segment playback)           │  │
│  │  • WebSocket Client (events/controls)                     │  │
│  │  • Now Playing · DJ Says · Controls · Decision Trace      │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────┬──────────────────┬─────────────────────┘
                         │ HTTP             │ WebSocket
                         │ (audio)          │ (events)
┌────────────────────────▼──────────────────▼─────────────────────┐
│                      FASTAPI BACKEND                             │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  DJ Loop (Background Task)                                  │ │
│  │  ├── Initialization Graph: Select → Download → TTS → Render │ │
│  │  └── Planning Graph: Plan → Cache → Download → Transition   │ │
│  │                       → Speech → TTS → Render → Emit        │ │
│  └────────────────────────────────────────────────────────────┘ │
│                              │                                   │
│  ┌───────────────────────────▼───────────────────────────────┐  │
│  │  LangGraph Agents                                          │  │
│  │  ├── TrackSelectorAgent   → Soundcharts + Gemini           │  │
│  │  ├── TransitionPlannerAgent → Gemini Audio Analysis        │  │
│  │  ├── SpeechWriterAgent    → Gemini (personalized humor)    │  │
│  │  ├── TTSAgent             → ElevenLabs                     │  │
│  │  ├── AudioRendererTool    → FFmpeg DJ Mix Engine           │  │
│  │  ├── PersistenceNode      → SQLite                         │  │
│  │  └── EmitEventsNode       → WebSocket                      │  │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Features

### ✅ Implemented

- **AI Track Selection**: Gemini selects tracks based on user preferences, mood, and history
- **Audio-Based Transition Planning**: Sends actual audio to Gemini 2.0 Flash for BPM/key/energy analysis
- **5 Transition Types**: Crossfade blend, bass swap, filter sweep, echo out, vinyl stop
- **DJ Speech Generation**: Personalized intros and transitions using user context file
- **ElevenLabs TTS**: High-quality voice synthesis for DJ commentary
- **HTTP Audio Streaming**: Gapless segment playback with prefetching
- **WebSocket Events**: Real-time now_playing, dj_says, decision_trace updates
- **Song Download**: Automatic acquisition via yt-dlp when songs aren't cached
- **50GB Cache Management**: LRU eviction based on play count
- **SQLite Persistence**: Sessions, plays, segments, LLM traces

### 🎛️ UI Controls

- Mode toggle (Autonomous / Guided)
- Mood slider (0 = calm → 1 = energetic)
- Freeform prompt input
- Skip track button
- Decision trace viewer

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- FFmpeg (must be in PATH)
- API Keys: OpenRouter, Soundcharts, ElevenLabs

### 1. Clone & Install

```bash
# Backend
pip install -r requirements.txt

# Frontend
cd frontend && npm install
```

### 2. Configure Environment

Create `.env` in the project root:

```bash
# Required
OPENROUTER_API_KEY=sk-or-...
SOUNDCHARTS_APP_ID=your-app-id
SOUNDCHARTS_API_KEY=your-api-key
ELEVENLABS_API_KEY=your-api-key

# Optional
ELEVENLABS_VOICE_ID=st7NwhTPEzqo2riw7qWC  # Default voice
```

### 3. Initialize Database

```bash
python backend/scripts/init_db.py
```

### 4. Add User Context (Optional)

Edit `data/user_context.txt` to personalize DJ commentary:

```text
User: Jamie (secretly a Swiftie)
Music Preferences:
- Pop and dance music
- 2010s nostalgia
- Upbeat workout tracks
DJ Style: Energetic with dry humor
```

### 5. Start the Application

**Terminal 1 - Backend:**
```bash
uvicorn backend.main:app --reload --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd frontend && npm run dev
```

### 6. Open Browser

Navigate to `http://localhost:5173` and click **▶️ Play DJ** to start!

## How It Works

### Segment-Based Architecture

The DJ generates **~3-4 minute audio segments** ahead of playback:

1. **Intro Segment**: First song with DJ intro speech
2. **Transition Segments**: Last 20s of Song A → crossfade → most of Song B

Each segment is pre-rendered with FFmpeg and served via HTTP. The frontend plays segments back-to-back with 0.2s overlap for gapless audio.

### AI Analysis Flow

When planning a transition:

1. **TrackSelectorAgent** picks next song based on preferences + history (no repeats)
2. **TransitionPlannerAgent** sends both audio files to Gemini 2.0 Flash
3. Gemini analyzes BPM, key, energy and recommends transition type
4. **SpeechWriterAgent** generates contextual DJ commentary
5. **TTSAgent** synthesizes speech with ElevenLabs
6. **AudioRendererTool** mixes everything with FFmpeg

## Project Structure

```
ai-dj/
├── backend/
│   ├── main.py                 # FastAPI app, WebSocket, HTTP endpoints
│   ├── orchestration/
│   │   ├── graph.py            # LangGraph agents & state machine
│   │   ├── loop.py             # Background DJ loop
│   │   └── events.py           # WebSocket event emitter
│   ├── integrations/
│   │   ├── openrouter.py       # Gemini LLM client
│   │   ├── soundcharts.py      # Song metadata API
│   │   └── elevenlabs.py       # TTS synthesis
│   ├── ai_analyzer.py          # Audio-based transition analysis
│   ├── dj_mix.py               # FFmpeg mix engine
│   ├── transitions.py          # FFmpeg filter implementations
│   ├── song_downloader.py      # yt-dlp wrapper
│   ├── cache_manager.py        # 50GB song cache with LRU
│   └── db.py                   # SQLite async operations
├── frontend/
│   └── src/
│       ├── App.tsx             # Main UI component
│       └── AudioStream.ts      # Gapless HTTP audio player
├── data/
│   ├── cache/songs/            # Downloaded MP3s
│   ├── segments/               # Rendered mix segments
│   ├── tts/                    # Generated TTS audio
│   └── user_context.txt        # User personalization
├── docs/                       # System documentation
└── requirements.txt
```

## API Endpoints

### HTTP

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/audio/segments/{file}` | GET | Stream rendered segments |
| `/audio/songs/{file}` | GET | Stream cached songs |
| `/webrtc/offer` | POST | WebRTC signaling (legacy) |

### WebSocket `/ws`

**Server → Client Events:**
```typescript
{ type: "playback_started", data: {...} }
{ type: "now_playing", data: { title, artist, artwork } }
{ type: "dj_says", data: { text } }
{ type: "segment_ready", data: { segment_url } }
{ type: "decision_trace", data: { trace: [...] } }
```

**Client → Server Controls:**
```typescript
{ type: "play" }
{ type: "skip" }
{ type: "set_mode", data: { mode: "autonomous" | "guided" } }
{ type: "set_mood", data: { mood: 0.0-1.0 } }
{ type: "prompt", data: { text: "..." } }
```

## Transition Types

| Type | Best For | Effect |
|------|----------|--------|
| `blend` | Similar tempo/energy | Standard crossfade |
| `bass_swap` | House/techno, groove maintenance | Swap bass at transition |
| `filter_sweep` | Harmonic clashes | LPF out, HPF in |
| `echo_out` | Dramatic exits, key clashes | Feedback delay tail |
| `vinyl_stop` | Genre/tempo changes | Turntable brake effect |

## Development

### Running Tests

```bash
pytest backend/ -v
```

### Populate Song Cache

Pre-download songs for faster startup:

```bash
python backend/scripts/populate_song_cache.py
```

### Render Demo Mix

Test the mix engine directly:

```bash
python backend/dj_mix.py song1.mp3 song2.mp3 bass_swap
```

## Documentation

- [`docs/DOCUMENTATION.md`](docs/DOCUMENTATION.md) - Complete system specification
- [`docs/transition-field-guide.md`](docs/transition-field-guide.md) - DJ transition strategies
- [`docs/contracts.md`](docs/contracts.md) - WebSocket message formats
- [`docs/SETUP_GUIDE.md`](docs/SETUP_GUIDE.md) - Detailed setup instructions

## Troubleshooting

**No audio playing?**
- Check browser console for WebSocket connection status
- Ensure FFmpeg is installed and in PATH
- Verify API keys are set in `.env`

**Songs not downloading?**
- Check yt-dlp is installed: `pip install yt-dlp`
- Some songs may not be available

**LLM errors?**
- Verify `OPENROUTER_API_KEY` is valid
- Check rate limits on OpenRouter dashboard

## License

Private project - All rights reserved.

---

*Built with ❤️ and a lot of FFmpeg filter debugging*
