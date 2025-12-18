# AI DJ Monorepo

> **A personal AI DJ that plays music continuously in your browser via WebRTC audio, while multiple async AI agents plan tracks, transitions (as FFmpeg filtergraphs), and occasional humorous "DJ talk" via ElevenLabs TTS.**

## High-Level Architecture

This monorepo houses the AI DJ project with:

- **frontend/**: React + TypeScript + Tailwind UI with WebRTC audio playback and WebSocket controls
- **backend/**: Python + FastAPI server with LangGraph multi-agent orchestration
- **docs/**: Complete documentation including system architecture, contracts, and implementation notes

### Tech Stack
- **Backend**: FastAPI + LangGraph + aiortc (WebRTC) + SQLite
- **LLM**: Gemini 2.5 Flash via OpenRouter (with thinking budget control)
- **Metadata**: Soundcharts API via official Python SDK (song features, lyrics, popularity)
- **TTS**: ElevenLabs Flash v2.5
- **Audio**: FFmpeg filtergraphs for transitions
- **Frontend**: Vite + React + Tailwind + Framer Motion

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- FFmpeg (in PATH)
- API keys: OpenRouter, Soundcharts, ElevenLabs

### Backend Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Initialize database:**
   ```bash
   python backend/scripts/init_db.py
   ```

4. **Start server:**
   ```bash
   uvicorn backend.main:app --reload --port 8000
   ```

### Frontend Setup

1. **Install and run:**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

2. **Open browser:**
   Navigate to `http://localhost:5173`

## Features

### Implemented ✅
- **Multi-Agent Orchestration**: 7 LangGraph agents (track selection, transition planning, speech writing, TTS, rendering, persistence, events)
- **WebRTC Audio Streaming**: Real-time audio delivery to browser
- **Database Layer**: SQLite with 8 tables for songs, features, lyrics, sessions, segments, LLM traces
- **External APIs**: Soundcharts, OpenRouter (Gemini), ElevenLabs integrations
- **Cache Management**: 50GB song cache with least-played eviction
- **Interactive UI**: Mode toggle, mood slider, prompt input, skip controls
- **Decision Transparency**: View AI decision traces in real-time

### In Progress 🚧
- Audio segment rendering with actual song files
- WebSocket event broadcasting to frontend
- Complete FFmpeg transition implementations
- Song acquisition/download logic

## Documentation

- **[DOCUMENTATION.md](docs/DOCUMENTATION.md)** - Complete system specification
- **[phase-completion-notes.md](docs/phase-completion-notes.md)** - Implementation details and how-to-run guide
- **[contracts.md](docs/contracts.md)** - WebSocket and WebRTC message formats
- **[repo-layout.md](docs/repo-layout.md)** - Folder structure and conventions

## Architecture

```
Frontend (React)
    ↕ WebSocket (events/controls)
    ↕ WebRTC (audio stream)
FastAPI Backend
    ↓
DJ Loop (background task)
    ↓
LangGraph Agents
    ├─ TrackSelectorAgent → Soundcharts + Gemini
    ├─ TransitionPlannerAgent → FFmpeg filtergraphs
    ├─ SpeechWriterAgent → Gemini (creative)
    ├─ TTSAgent → ElevenLabs
    ├─ AudioRendererTool → FFmpeg
    ├─ PersistenceNode → SQLite
    └─ EmitEventsNode → WebSocket
```

## Testing

```bash
# Backend tests
pytest backend/ -v

# Integration tests
pytest backend/test_integration.py -v
```

## Project Structure

```
/
├── backend/
│   ├── main.py                 # FastAPI app with WebRTC
│   ├── db.py                   # Database operations
│   ├── cache_manager.py        # Song cache management
│   ├── ffmpeg_runner.py        # Safe filtergraph execution
│   ├── integrations/           # External API clients
│   │   ├── soundcharts.py
│   │   ├── openrouter.py
│   │   └── elevenlabs.py
│   ├── orchestration/          # LangGraph agents
│   │   ├── graph.py            # Agent nodes and graph
│   │   ├── loop.py             # DJ background loop
│   │   └── events.py           # WebSocket emitter
│   └── scripts/
│       └── init_db.py          # Database initialization
├── frontend/
│   └── src/
│       ├── App.tsx             # Main UI component
│       └── WebRTC.ts           # WebRTC client
├── docs/                       # Complete documentation
├── .env.example                # Environment template
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

## Contributing

This is a personal project following the AI DJ specification. See [docs/DOCUMENTATION.md](docs/DOCUMENTATION.md) for the complete system design.

## License

Private project - All rights reserved.


