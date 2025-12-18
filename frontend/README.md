# Frontend App

## Run Instructions

To run the frontend app, follow these steps:

1. Install dependencies:
   ```bash
   npm install
   ```
2. Start the development server:
   ```bash
   npm run dev
   ```
3. Open your browser and navigate to `http://localhost:3000` (or the port specified in your Vite config).

## Environment Variables

Make sure to set the following environment variables in your `.env` file:

- `VITE_WS_URL`: WebSocket URL for connecting to the backend.
- `VITE_API_URL`: API URL for WebRTC offers.
