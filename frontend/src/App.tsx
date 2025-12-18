import React, { useEffect, useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { useAudioStream } from './AudioStream';
import './App.css';

const App: React.FC = () => {
  const [nowPlaying, setNowPlaying] = useState({ title: '', artist: '', artwork: '' });
  const [djSays, setDjSays] = useState('');
  const [upNext, setUpNext] = useState<string[]>([]);
  const [decisionTrace, setDecisionTrace] = useState<string[]>([]);
  const [cacheStatus, setCacheStatus] = useState({ usedBytes: 0, limitBytes: 0 });
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting');
  const [mode, setMode] = useState<'autonomous' | 'guided'>('autonomous');
  const [mood, setMood] = useState(0.5);
  const [genres, setGenres] = useState<string[]>(['pop']);
  const [prompt, setPrompt] = useState('');
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [audioStarted, setAudioStarted] = useState(false);
  const wsRef = React.useRef<WebSocket | null>(null);

  // Memoize callback to prevent useEffect re-runs in AudioStream
  const handlePlaybackStarted = useCallback(() => {
    setAudioStarted(true);
  }, []);

  // HTTP audio streaming (backend handles all transitions)
  const { isPlaying } = useAudioStream({
    ws,
    onPlaybackStarted: handlePlaybackStarted
  });
  
  const handleStartAudio = () => {
    // Unlock audio context by playing silent audio immediately on user click
    // This is required by browsers to allow audio playback later
    const unlockAudio = () => {
      const audio = new Audio();
      audio.src = 'data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA';
      audio.volume = 0.01;
      audio.play().then(() => {
        console.log('🔓 Audio context unlocked');
        audio.pause();
      }).catch((e) => {
        console.log('Audio unlock attempt:', e.message);
      });
    };
    
    unlockAudio();
    
    // Send play command to backend via WebSocket
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'play' }));
      console.log('Play command sent to backend');
      // Audio will start when segment_ready event is received
    }
  };

  useEffect(() => {
    // Don't create a new WebSocket if one already exists and is open/connecting
    if (wsRef.current) {
      const state = wsRef.current.readyState;
      if (state === WebSocket.OPEN || state === WebSocket.CONNECTING) {
        console.log('WebSocket already exists and is active, skipping');
        return;
      }
      // If websocket exists but is closed/closing, clean it up first
      if (state === WebSocket.CLOSED || state === WebSocket.CLOSING) {
        console.log('Cleaning up closed WebSocket before creating new one');
        wsRef.current.onopen = null;
        wsRef.current.onclose = null;
        wsRef.current.onerror = null;
        wsRef.current.onmessage = null;
        wsRef.current = null;
        setWs(null);
      }
    }
    
    const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws';
    const websocket = new WebSocket(wsUrl);
    const currentWs = websocket; // Capture reference for cleanup
    wsRef.current = websocket;
    setWs(websocket);
    setConnectionStatus('connecting'); // Set status immediately

    websocket.onopen = () => {
      console.log('WebSocket connected');
      // Only update if this is still the current websocket
      if (wsRef.current === currentWs && currentWs.readyState === WebSocket.OPEN) {
        setConnectionStatus('connected');
      }
    };

    websocket.onclose = (event) => {
      // Don't log if this was a normal cleanup
      if (event.code !== 1000 && wsRef.current === currentWs) {
        console.log('WebSocket disconnected unexpectedly');
      }
      // Only update if this is still the current websocket
      if (wsRef.current === currentWs) {
        setConnectionStatus('disconnected');
        wsRef.current = null;
        setWs(null);
      }
    };

    websocket.onerror = (error) => {
      // Only log if this is still the current websocket and not already closed
      if (wsRef.current === currentWs && currentWs.readyState !== WebSocket.CLOSED) {
        console.error('WebSocket error:', error);
        setConnectionStatus('disconnected');
      }
    };

    websocket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('WebSocket message:', data);
        
        // Handle events based on the contract
        switch (data.type) {
          case 'playback_started':
            console.log('Playback started:', data.data);
            setAudioStarted(true);
            break;
          case 'now_playing':
            setNowPlaying(data.data || data.payload);
            break;
          case 'dj_says':
            setDjSays(data.data?.text || data.payload);
            break;
          case 'up_next':
            setUpNext(data.data?.songs || data.payload || []);
            break;
          case 'decision_trace':
            setDecisionTrace(prev => [...prev, data.data?.why || data.payload]);
            break;
          case 'segment_ready':
            // Segment ready is handled by AudioStream hook
            console.log('Segment ready event received in App:', data.data);
            break;
          case 'cache_status':
            setCacheStatus(data.data || { usedBytes: 0, limitBytes: 0 });
            break;
          default:
            console.log('Unknown event type:', data.type);
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    return () => {
      // Only cleanup if this websocket is still the current one
      if (wsRef.current === currentWs) {
        const readyState = currentWs.readyState;
        // Only close if actually connected or connecting (not CLOSED or CLOSING)
        if (readyState === WebSocket.OPEN || readyState === WebSocket.CONNECTING) {
          console.log('Cleaning up WebSocket');
          // Remove event listeners first to prevent error callbacks
          currentWs.onopen = null;
          currentWs.onclose = null;
          currentWs.onerror = null;
          currentWs.onmessage = null;
          currentWs.close();
        }
        // Only clear refs if this is still the current websocket
        if (wsRef.current === currentWs) {
          wsRef.current = null;
          setWs(null);
        }
      }
    };
  }, []);

  const handleControl = (controlType: string, payload?: any) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: controlType, data: payload }));
    }
  };

  const handleSkip = () => {
    handleControl('skip');
  };

  const handleModeToggle = () => {
    const newMode = mode === 'autonomous' ? 'guided' : 'autonomous';
    setMode(newMode);
    handleControl('set_mode', { mode: newMode });
  };

  const handleMoodChange = (value: number) => {
    setMood(value);
    handleControl('set_mood', { mood: value });
  };

  const handlePromptSubmit = () => {
    if (prompt.trim()) {
      handleControl('prompt', { text: prompt });
      setPrompt('');
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-900 via-blue-900 to-black text-white p-8">
      {/* Connection Status */}
      <div className="mb-4 flex items-center gap-4">
        <div className="text-sm">
          Status: <span className={connectionStatus === 'connected' ? 'text-green-400' : 'text-red-400'}>
            {connectionStatus}
          </span>
        </div>
        
        {/* Play DJ Button - Starts the DJ pipeline */}
        {!audioStarted && (
          <motion.button
            onClick={handleStartAudio}
            disabled={connectionStatus !== 'connected'}
            className={`font-bold py-2 px-6 rounded-lg shadow-lg transition ${
              connectionStatus === 'connected' 
                ? 'bg-green-500 hover:bg-green-600 text-white cursor-pointer' 
                : 'bg-gray-500 text-gray-300 cursor-not-allowed'
            }`}
            initial={{ scale: 0.9 }}
            animate={connectionStatus === 'connected' ? { scale: [0.9, 1.05, 1] } : {}}
            transition={{ repeat: connectionStatus === 'connected' ? Infinity : 0, duration: 1.5 }}
          >
            {connectionStatus === 'connected' ? '▶️ Play DJ' : '⏸️ Connecting...'}
          </motion.button>
        )}
        
        {audioStarted && (
          <span className="text-green-400 text-sm">
            🎵 Audio Active
          </span>
        )}
      </div>

      {/* Now Playing */}
      <motion.div 
        className="bg-white/10 backdrop-blur-lg rounded-lg p-6 mb-6"
        initial={{ opacity: 0, y: 20 }} 
        animate={{ opacity: 1, y: 0 }}
      >
        <h2 className="text-2xl font-bold mb-4">Now Playing</h2>
        {nowPlaying.artwork && <img src={nowPlaying.artwork} alt={nowPlaying.title} className="w-48 h-48 rounded-lg mb-4" />}
        <p className="text-xl">{nowPlaying.title || 'No track playing'}</p>
        <p className="text-gray-300">{nowPlaying.artist || ''}</p>
      </motion.div>

      {/* DJ Says */}
      {djSays && (
        <motion.div 
          className="bg-purple-500/20 backdrop-blur-lg rounded-lg p-6 mb-6"
          initial={{ opacity: 0, x: -20 }} 
          animate={{ opacity: 1, x: 0 }}
        >
          <h2 className="text-xl font-bold mb-2">DJ Says</h2>
          <p className="italic">{djSays}</p>
        </motion.div>
      )}

      {/* Controls */}
      <div className="bg-white/10 backdrop-blur-lg rounded-lg p-6 mb-6">
        <h2 className="text-xl font-bold mb-4">Controls</h2>
        
        {/* Mode Toggle */}
        <div className="mb-4">
          <label className="block mb-2">Mode:</label>
          <button 
            onClick={handleModeToggle}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg transition"
          >
            {mode === 'autonomous' ? 'Autonomous' : 'Guided'}
          </button>
        </div>

        {/* Mood Slider */}
        <div className="mb-4">
          <label className="block mb-2">Mood: {mood.toFixed(2)} (0=calm, 1=energetic)</label>
          <input 
            type="range" 
            min="0" 
            max="1" 
            step="0.01" 
            value={mood}
            onChange={(e) => handleMoodChange(parseFloat(e.target.value))}
            className="w-full"
          />
        </div>

        {/* Prompt Input */}
        <div className="mb-4">
          <label className="block mb-2">Prompt:</label>
          <div className="flex gap-2">
            <input 
              type="text" 
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handlePromptSubmit()}
              placeholder="e.g., 'Play something from the 2010s'"
              className="flex-1 px-4 py-2 bg-white/20 rounded-lg"
            />
            <button 
              onClick={handlePromptSubmit}
              className="px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg transition"
            >
              Send
            </button>
          </div>
        </div>

        {/* Skip Button */}
        <button 
          onClick={handleSkip}
          className="px-6 py-3 bg-red-600 hover:bg-red-700 rounded-lg transition font-bold"
        >
          Skip Track
        </button>
      </div>

      {/* Up Next */}
      <motion.div 
        className="bg-white/10 backdrop-blur-lg rounded-lg p-6 mb-6"
        initial={{ opacity: 0, y: 20 }} 
        animate={{ opacity: 1, y: 0 }}
      >
        <h2 className="text-xl font-bold mb-4">Up Next</h2>
        <ul className="space-y-2">
          {upNext.length > 0 ? upNext.map((track, index) => (
            <li key={index} className="text-gray-300">{track}</li>
          )) : <li className="text-gray-500">No upcoming tracks</li>}
        </ul>
      </motion.div>

      {/* Decision Trace */}
      {decisionTrace.length > 0 && (
        <motion.div 
          className="bg-white/10 backdrop-blur-lg rounded-lg p-6 mb-6"
          initial={{ opacity: 0 }} 
          animate={{ opacity: 1 }}
        >
          <h2 className="text-xl font-bold mb-4">Decision Trace</h2>
          <ul className="space-y-1 text-sm">
            {decisionTrace.slice(-5).map((trace, index) => (
              <li key={index} className="text-gray-400">{trace}</li>
            ))}
          </ul>
        </motion.div>
      )}

      {/* Cache Status */}
      <div className="bg-white/10 backdrop-blur-lg rounded-lg p-4">
        <h3 className="text-sm font-bold mb-2">Cache Status</h3>
        <p className="text-xs text-gray-400">
          {(cacheStatus.usedBytes / 1e9).toFixed(2)} GB / {(cacheStatus.limitBytes / 1e9).toFixed(2)} GB
        </p>
      </div>
    </div>
  );
};

export default App;
