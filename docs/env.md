# Environment Variables

This document lists all environment variables used by the frontend and backend services in the AI DJ project.

## Frontend Environment Variables

- `VITE_API_URL` - the base URL for REST API calls to the backend
- `VITE_WS_URL` - WebSocket URL for real-time communication with the backend
- `OPENROUTER_API_KEY` - API key for integration with OpenRouter or other external services (used by frontend app)

## Backend Environment Variables

- `BACKEND_PORT` - port on which the backend FastAPI server runs
- `MCP_API_KEY` - API key for MCP service integration used by backend
- `WEBRTC_ICE_SERVERS` - comma-separated list of WebRTC ICE server URLs for signaling and NAT traversal

## Notes

- Environment variables must be set appropriately in local `.env` file or environment before run.
- Frontend expects variables prefixed with `VITE_` to be exposed to the client.
- API keys must never be committed to version control.

Refer to `.env.example` for a template of variable names to be used locally.


