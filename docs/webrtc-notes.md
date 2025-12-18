# WebRTC Audio Delivery - Implementation Notes

## Current Status
- Implemented `/webrtc/offer` endpoint in backend to accept SDP offers and respond with SDP answers.
- Used aiortc's `RTCPeerConnection` with a custom `AudioStreamTrack` to send real-time audio.
- Audio source is currently a test tone generator producing a steady 440Hz sine wave at 48kHz.
- Non-trickle ICE is used; all ICE candidates bundled in SDP answer to simplify signaling.
- Connection state changes monitored to cleanup and close peer connections on failure or disconnect.

## Signaling Payload Format
- Client sends POST to `/webrtc/offer` with JSON body containing:
  ```json
  {
    "sdp": "<SDP offer string>",
    "type": "offer"
  }
  ```
- Server responds with JSON containing:
  ```json
  {
    "sdp": "<SDP answer string>",
    "type": "answer"
  }
  ```

## How to Run Locally
- Install dependencies: `pip install -r requirements.txt` including `aiortc`, `numpy`.
- Start backend server as usual.
- Use frontend that sends WebRTC SDP offer to `/webrtc/offer` and establishes connection.
- Confirm audio from backend received in browser with no microphone permission prompt.

## Known Issues & TODOs
- Peer connection cleanup on client disconnect is basic; could be improved.
- No support for trickle ICE signaling yet; consider adding WebSocket signaling later.
- Audio currently test tone; will later integrate DJ audio rendering pipeline.
- No advanced error handling or reconnection logic.

## Additional Notes
- Audio frames generated at 48 kHz, mono, 20ms per frame.
- Silence frames emitted to prevent underflow if audio queue is empty.

