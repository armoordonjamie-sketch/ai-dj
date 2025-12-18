# Replace WebRTC with HTTP Audio Streaming

## Problem
WebRTC audio streaming is causing stuttering and complexity issues. Replace with simple HTTP streaming like Spotify uses - serve audio files via HTTP endpoints with range request support.

## Solution
Use FastAPI static file serving with HTTP range request support. Frontend uses HTML5 audio element that automatically handles streaming, buffering, and seeking.

## Architecture

```
Backend: FastAPI → HTTP endpoint → Serve audio files/segments
Frontend: HTML5 Audio Element → Streams from HTTP URL → Automatic buffering
```

## Implementation Steps

### 1. Create HTTP Audio Streaming Endpoints

**File: `backend/main.py`**

- Remove WebRTC imports and code (`aiortc`, `RTCPeerConnection`, etc.)
- Remove `audio_queue`, `peer_connections`, `audio_track_instance`, `tone_task` globals
- Add static file serving for segments: `app.mount("/audio/segments", StaticFiles(directory="data/segments"), name="segments")`
- Add static file serving for songs: `app.mount("/audio/songs", StaticFiles(directory="data/cache/songs"), name="songs")`
- Create endpoint `/api/audio/current` that returns current playing segment URL
- Create endpoint `/api/audio/next` that returns next segment URL when ready
- Add HTTP range request support using `FileResponse` with `range` header handling

### 2. Update DJ Loop to Emit Segment URLs

**File: `backend/orchestration/loop.py`**

- Remove all WebRTC-related code (`audio_queue`, `_bridge_queue`, `_run_audio_producer_thread`, `_bridge_queue_to_audio_queue`)
- Remove `audio_queue` parameter from `__init__`
- When segment is rendered, emit WebSocket event with segment URL: `{"type": "segment_ready", "data": {"url": "/audio/segments/segment_xxx.wav"}}`
- When initial song is ready, emit event with song URL: `{"type": "playback_started", "data": {"song_url": "/audio/songs/..."}}`

### 3. Update Frontend to Use HTML5 Audio

**File: `frontend/src/WebRTC.ts`**

- Remove entire WebRTC implementation
- Create new `AudioStream.ts` that:
  - Manages HTML5 audio element
  - Listens for WebSocket events (`segment_ready`, `playback_started`)
  - Updates `audioElement.src` when new segment is ready
  - Handles seamless transitions between segments
  - Implements preloading of next segment

**File: `frontend/src/App.tsx`**

- Remove `useWebRTC()` import and call
- Import `useAudioStream()` instead
- Update `handleStartAudio` to just send play command (audio starts automatically when segment URL is received)

### 4. Implement Seamless Segment Transitions

**File: `frontend/src/AudioStream.ts`**

- Use two audio elements for crossfading:
  - `currentAudio`: Currently playing segment
  - `nextAudio`: Preloaded next segment
- When `segment_ready` event received:
  - Preload next segment in `nextAudio`
  - When current segment is near end (e.g., last 1 second), start crossfading
  - Crossfade: fade out current, fade in next
  - Swap references when transition complete

### 5. Add HTTP Range Request Support

**File: `backend/main.py`**

- Create custom endpoint for audio files that handles `Range` headers:
  ```python
  @app.get("/audio/segments/{filename}")
  async def serve_segment(filename: str, request: Request):
      # Handle Range header for seeking/buffering
      # Return 206 Partial Content with appropriate headers
  ```

### 6. Cleanup WebRTC Code

- Delete `backend/webrtc_audio.py`
- Remove WebRTC dependencies from `requirements.txt` (if any)
- Remove WebRTC endpoint `/webrtc/offer` from `main.py`
- Update `docs/DOCUMENTATION.md` to reflect HTTP streaming instead of WebRTC

## Key Changes

**Backend:**
1. `backend/main.py`: Remove WebRTC, add static file serving and audio endpoints
2. `backend/orchestration/loop.py`: Remove audio queue/producer thread, emit URLs instead
3. `backend/orchestration/events.py`: Ensure events include file URLs

**Frontend:**
1. `frontend/src/AudioStream.ts`: New file for HTML5 audio management
2. `frontend/src/App.tsx`: Replace WebRTC with AudioStream
3. `frontend/src/WebRTC.ts`: Delete or repurpose

## Benefits

- Simpler architecture - no WebRTC complexity
- Better browser compatibility - HTML5 audio works everywhere
- Automatic buffering - browser handles it
- Seeking support - HTTP range requests enable seeking
- Easier debugging - can directly access audio URLs
- No real-time frame synchronization issues

## Testing

After implementation:
- Verify segments stream smoothly
- Test seeking/scrubbing works
- Verify seamless transitions between segments
- Check browser buffering behavior
- Test with slow network (should buffer automatically)

