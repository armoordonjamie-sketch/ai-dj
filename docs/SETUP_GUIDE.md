# AI DJ Setup Guide

This guide will help you get the AI DJ system up and running.

## Prerequisites

- **Python 3.10+** - [Download Python](https://www.python.org/downloads/)
- **Node.js 18+** - [Download Node.js](https://nodejs.org/)
- **FFmpeg** - [Download FFmpeg](https://ffmpeg.org/download.html)
- **API Keys** (see below)

## Step 1: Get API Keys

You'll need accounts and API keys from three services:

### 1. OpenRouter (for Gemini 2.5 Flash LLM)
1. Go to [OpenRouter](https://openrouter.ai/)
2. Sign up for an account
3. Navigate to [API Keys](https://openrouter.ai/keys)
4. Create a new API key
5. Copy the key (starts with `sk-or-v1-...`)

### 2. Soundcharts (for song metadata)
1. Go to [Soundcharts](https://soundcharts.com/)
2. Sign up for an API subscription
3. Get your **App ID** and **API Key** from your account dashboard
4. You'll need both values

### 3. ElevenLabs (for text-to-speech)
1. Go to [ElevenLabs](https://elevenlabs.io/)
2. Sign up for an account
3. Navigate to [Profile Settings](https://elevenlabs.io/app/settings/api-keys)
4. Copy your API key
5. (Optional) The default voice ID `st7NwhTPEzqo2riw7qWC` is already configured

## Step 2: Backend Setup

### 2.1 Install Python Dependencies

```bash
# From project root
pip install -r requirements.txt
```

**Note**: This includes the official Soundcharts Python SDK and yt-dlp. If you get import errors, make sure they're installed:
```bash
pip install soundcharts yt-dlp
```

**Important**: yt-dlp requires FFmpeg for audio extraction. Install FFmpeg:
- **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH
- **Mac**: `brew install ffmpeg`
- **Linux**: `sudo apt-get install ffmpeg`

### 2.2 Configure Environment Variables

```bash
# Copy the example file
cp .env.example .env
```

Now edit `.env` and add your API keys:

```bash
# OpenRouter API (for Gemini 2.5 Flash)
OPENROUTER_API_KEY=sk-or-v1-YOUR-KEY-HERE

# Soundcharts API (both required)
SOUNDCHARTS_APP_ID=your-app-id-here
SOUNDCHARTS_API_KEY=your-api-key-here

# ElevenLabs TTS
ELEVENLABS_API_KEY=your-elevenlabs-key-here

# Optional: customize these if needed
# DB_PATH=data/persistence.db
# SONG_CACHE_DIR=data/cache/songs
# SEGMENT_DIR=data/segments
# TTS_DIR=data/tts
# CACHE_MAX_BYTES=50000000000
# BACKEND_PORT=8000
```

### 2.3 Validate Configuration

Run the validation script to check your setup:

```bash
python backend/validate_config.py
```

You should see:
```
✅ All required configuration is set!
🚀 Ready to start AI DJ server!
```

If you see errors, make sure all API keys are correctly set in `.env`.

### 2.4 Initialize Database

```bash
python backend/scripts/init_db.py
```

You should see:
```
Database initialized successfully.
```

### 2.5 Populate Song Cache (Optional but Recommended)

Before running the DJ, download some songs to the cache:

```bash
# Download a curated list of popular songs (~8 songs)
python backend/scripts/populate_song_cache.py
```

This will download songs to `backend/song-cache/`. You can also download individual songs:

```bash
# Download a specific song
python backend/song_downloader.py "Taylor Swift Shake It Off"

# With artist and title metadata
python backend/song_downloader.py "shake it off" "Taylor Swift" "Shake It Off"
```

### 2.6 Start Backend Server

```bash
uvicorn backend.main:app --reload --port 8000
```

The server should start without errors. Check the logs for:
- ✅ "Database connected"
- ✅ "DJ Loop started"
- ✅ "Application startup complete"

If you see warnings like:
- ⚠️ "OPENROUTER_API_KEY not set" - Add your API key to `.env`
- ⚠️ "SOUNDCHARTS credentials not set" - Add both app_id and api_key to `.env`

## Step 3: Frontend Setup

### 3.1 Install Node Dependencies

```bash
cd frontend
npm install
```

### 3.2 Configure Frontend Environment

Create `frontend/.env`:

```bash
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws
```

### 3.3 Start Frontend Dev Server

```bash
npm run dev
```

The frontend should start at `http://localhost:5173` (or another port if 5173 is busy).

## Step 4: Test the System

1. **Open your browser** to `http://localhost:5173`

2. **Check connection status** in the top-left corner:
   - Should show "connected" in green

3. **Check browser console** (F12):
   - Should see "WebSocket connected"
   - Should see "WebRTC connection established"

4. **Check backend logs**:
   - Should see DJ Loop executing
   - Should see agent nodes running

## Troubleshooting

### Backend won't start

**Error: "Header value must be str or bytes, not <class 'NoneType'>"**
- **Cause**: API keys not set in `.env`
- **Fix**: Run `python backend/validate_config.py` to check which keys are missing

**Error: "401 Unauthorized" from OpenRouter**
- **Cause**: Invalid or missing OpenRouter API key
- **Fix**: Check your API key at https://openrouter.ai/keys

**Error: Database errors**
- **Cause**: Database not initialized
- **Fix**: Run `python backend/scripts/init_db.py`

### Frontend won't connect

**WebSocket shows "disconnected"**
- **Cause**: Backend not running
- **Fix**: Start backend with `uvicorn backend.main:app --reload`

**WebRTC audio not working**
- **Cause**: Browser permissions or backend issue
- **Fix**: Check browser console for errors, try Chrome/Edge

### No songs playing

**DJ Loop runs but no audio**
- **Cause**: No song files in cache
- **Fix**: Add MP3 files to `backend/song-cache/` directory
- **Note**: Song acquisition is not yet implemented - you need to manually add files

## Next Steps

Once everything is running:

1. **Test controls**: Try the skip button, mood slider, and prompt input
2. **Monitor logs**: Watch the backend logs to see agent decisions
3. **Check database**: Use SQLite browser to view `data/persistence.db`
4. **Add songs**: Place MP3 files in `backend/song-cache/` for the DJ to use

## Getting Help

- Check [phase-completion-notes.md](./phase-completion-notes.md) for detailed documentation
- Review [DOCUMENTATION.md](./DOCUMENTATION.md) for system architecture
- Check backend logs for specific error messages
- Verify all API keys are valid and have sufficient credits

## API Key Costs

- **OpenRouter**: Pay-per-use, Gemini 2.5 Flash is very affordable (~$0.001 per request)
- **Soundcharts**: Subscription required, check their pricing
- **ElevenLabs**: Free tier available, then pay-per-character

Make sure you have credits/subscription for each service before running the system.

