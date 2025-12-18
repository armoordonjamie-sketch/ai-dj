# Frontend Implementation Notes

## What Was Implemented
- Created a Vite + React + TypeScript frontend app.
- Integrated Tailwind CSS for styling.
- Used Motion for subtle UI animations.
- Implemented WebSocket client for event handling and controls.
- Set up WebRTC for receive-only audio playback.

## Current Status
- The development server is running successfully with the command `npm install && npm run dev`.
- All UI components are functional, including the Now Playing card, DJ Says panel, and Up Next list.
- WebSocket connection is established, and events are being handled as per the contract.
- WebRTC functionality is implemented, allowing for audio playback from the backend.

## File List
- `frontend/src/App.tsx`: Main application component with UI and WebSocket handling.
- `frontend/src/WebRTC.ts`: Custom hook for WebRTC functionality.
- `frontend/src/index.css`: Tailwind CSS styles.
- `frontend/src/main.tsx`: Entry point for the React application.
- `frontend/README.md`: Instructions for running the frontend.

## Environment Variables
- `VITE_WS_URL`: WebSocket URL for backend connection.
- `VITE_API_URL`: API URL for WebRTC offers.

## WebSocket Event Handling
- Connects to the backend WebSocket using the URL from the environment variable.
- Handles events as specified in `/docs/contracts.md`:
  - `nowPlaying`: Updates the Now Playing card.
  - `djSays`: Updates the DJ Says panel.
  - `upNext`: Updates the Up Next list.

## WebRTC Flow Summary
- Creates an `RTCPeerConnection` for receiving audio.
- Sends a POST request to the backend with the offer to establish a connection.
- Attaches the received audio track to an `<audio autoplay />` element.

## TODOs
- Implement additional UI controls as needed.