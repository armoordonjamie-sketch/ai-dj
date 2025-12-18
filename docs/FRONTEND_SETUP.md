# Frontend Setup Guide

## Overview

The AI DJ frontend is built with:
- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Fast build tool and dev server
- **Tailwind CSS** - Utility-first styling
- **Framer Motion** - Smooth animations
- **WebRTC** - Real-time audio streaming
- **WebSocket** - Real-time event updates

## Quick Start

### 1. Install Dependencies

```bash
cd frontend
npm install
```

### 2. Configure Environment (Optional)

Create `frontend/.env` if you need custom URLs:

```bash
# Backend API URL
VITE_API_URL=http://localhost:8000

# WebSocket URL
VITE_WS_URL=ws://localhost:8000/ws
```

**Note**: These are the defaults, so you only need this file if using different ports.

### 3. Start Development Server

```bash
npm run dev
```

The frontend will start on **http://localhost:5173**

### 4. Build for Production

```bash
npm run build
```

Output will be in `frontend/dist/`

## Features

### Real-Time Audio Streaming
- Uses WebRTC for low-latency audio delivery
- Automatically connects to backend on load
- Displays connection status

### Live Updates via WebSocket
- **Now Playing**: Current track info and artwork
- **DJ Says**: AI-generated commentary
- **Up Next**: Upcoming tracks
- **Decision Trace**: AI reasoning (last 5 decisions)
- **Cache Status**: Song cache usage

### Interactive Controls
- **Mode Toggle**: Switch between Autonomous and Guided modes
- **Mood Slider**: Adjust energy level (0=calm, 1=energetic)
- **Prompt Input**: Give the DJ instructions (e.g., "Play something from the 2010s")
- **Skip Button**: Skip to next track

## Project Structure

```
frontend/
├── src/
│   ├── App.tsx           # Main application component
│   ├── App.css           # App-specific styles
│   ├── main.tsx          # React entry point
│   ├── index.css         # Global styles + Tailwind
│   └── WebRTC.ts         # WebRTC hook for audio streaming
├── index.html            # HTML template
├── package.json          # Dependencies and scripts
├── vite.config.ts        # Vite configuration
├── tsconfig.json         # TypeScript configuration
├── tailwind.config.js    # Tailwind CSS configuration
└── postcss.config.js     # PostCSS configuration
```

## Development

### Available Scripts

```bash
# Start dev server (with hot reload)
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Lint code
npm run lint
```

### Hot Module Replacement (HMR)

Vite provides instant HMR - changes appear immediately without full page reload.

### Proxy Configuration

The dev server proxies API and WebSocket requests to the backend:
- `/api/*` → `http://localhost:8000/api/*`
- `/ws` → `ws://localhost:8000/ws`

This avoids CORS issues during development.

## UI Components

### Now Playing Card
- Displays current track title, artist, and artwork
- Animated entrance with Framer Motion
- Glassmorphism design (backdrop blur)

### DJ Says Card
- Shows AI-generated commentary
- Appears when DJ has something to say
- Purple-tinted background

### Controls Panel
- Mode toggle button (Autonomous/Guided)
- Mood slider (0.0 to 1.0)
- Prompt input field
- Skip track button

### Up Next List
- Shows upcoming tracks
- Updates in real-time
- Empty state when no tracks queued

### Decision Trace
- Shows last 5 AI decisions
- Helps understand DJ's reasoning
- Collapsible/expandable

### Cache Status
- Displays cache usage (GB)
- Shows limit and current usage
- Updates in real-time

## Styling

### Tailwind CSS

The app uses Tailwind's utility classes for styling:

```tsx
<div className="bg-white/10 backdrop-blur-lg rounded-lg p-6">
  {/* Glassmorphism card */}
</div>
```

### Custom Theme

Custom colors defined in `tailwind.config.js`:
- `dj-purple`: #8B5CF6
- `dj-pink`: #EC4899
- `dj-blue`: #3B82F6

### Animations

Framer Motion provides smooth animations:

```tsx
<motion.div 
  initial={{ opacity: 0, y: 20 }} 
  animate={{ opacity: 1, y: 0 }}
>
  {/* Animated content */}
</motion.div>
```

## WebSocket Events

### Incoming Events (Backend → Frontend)

```typescript
// Now Playing
{
  type: 'now_playing',
  data: {
    title: string,
    artist: string,
    artwork: string
  }
}

// DJ Says
{
  type: 'dj_says',
  data: {
    text: string
  }
}

// Up Next
{
  type: 'up_next',
  data: {
    songs: string[]
  }
}

// Decision Trace
{
  type: 'decision_trace',
  data: {
    why: string
  }
}

// Cache Status
{
  type: 'cache_status',
  data: {
    usedBytes: number,
    limitBytes: number
  }
}
```

### Outgoing Events (Frontend → Backend)

```typescript
// Skip Track
{
  type: 'skip'
}

// Set Mode
{
  type: 'set_mode',
  data: {
    mode: 'autonomous' | 'guided'
  }
}

// Set Mood
{
  type: 'set_mood',
  data: {
    mood: number  // 0.0 to 1.0
  }
}

// Send Prompt
{
  type: 'prompt',
  data: {
    text: string
  }
}
```

## WebRTC Audio

### How It Works

1. **Frontend** creates RTCPeerConnection
2. **Frontend** generates SDP offer
3. **Frontend** sends offer to `/webrtc/offer` endpoint
4. **Backend** creates answer with audio track
5. **Frontend** receives answer and sets remote description
6. **Audio** streams from backend to frontend

### Audio Element

The WebRTC hook automatically creates an `<audio>` element:

```html
<audio id="webrtc-audio" autoplay></audio>
```

This element receives the audio stream and plays it automatically.

## Troubleshooting

### Frontend Won't Start

**Problem**: `npm run dev` fails
**Solution**: 
```bash
# Delete node_modules and reinstall
rm -rf node_modules package-lock.json
npm install
```

### WebSocket Not Connecting

**Problem**: "WebSocket disconnected" status
**Solution**:
1. Ensure backend is running on port 8000
2. Check `VITE_WS_URL` in `.env`
3. Check browser console for errors

### WebRTC Audio Not Playing

**Problem**: No audio heard
**Solution**:
1. Check browser console for WebRTC errors
2. Ensure backend `/webrtc/offer` endpoint is working
3. Check browser audio permissions
4. Try clicking on the page (some browsers require user interaction)

### CORS Errors

**Problem**: API requests blocked by CORS
**Solution**: 
- In development, Vite proxy handles this automatically
- In production, ensure backend has proper CORS headers

### Build Fails

**Problem**: `npm run build` fails
**Solution**:
```bash
# Check TypeScript errors
npx tsc --noEmit

# Fix linting issues
npm run lint
```

## Production Deployment

### Build

```bash
npm run build
```

### Serve Static Files

The `dist/` folder contains static files. Serve with:

```bash
# Using Python
python -m http.server 5173 --directory dist

# Using Node.js serve
npx serve dist -p 5173

# Using Nginx (production)
# Configure nginx to serve dist/ folder
```

### Environment Variables

For production, set environment variables at build time:

```bash
VITE_API_URL=https://api.your-domain.com npm run build
```

## Browser Compatibility

- **Chrome/Edge**: Full support ✅
- **Firefox**: Full support ✅
- **Safari**: Full support ✅
- **Mobile**: Supported (may need user interaction for audio)

## Performance

- **Initial Load**: ~100-200ms (with Vite)
- **HMR**: <50ms (instant updates)
- **Build Time**: ~5-10 seconds
- **Bundle Size**: ~150KB gzipped

## Next Steps

1. **Customize UI**: Edit `App.tsx` and Tailwind classes
2. **Add Features**: Implement playlist view, history, etc.
3. **Improve UX**: Add loading states, error boundaries
4. **Mobile Optimization**: Responsive design improvements
5. **PWA**: Add service worker for offline support

## References

- [React Documentation](https://react.dev/)
- [Vite Documentation](https://vitejs.dev/)
- [Tailwind CSS](https://tailwindcss.com/)
- [Framer Motion](https://www.framer.com/motion/)
- [WebRTC API](https://developer.mozilla.org/en-US/docs/Web/API/WebRTC_API)

