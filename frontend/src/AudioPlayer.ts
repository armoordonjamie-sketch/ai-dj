import { useEffect, useRef, useState } from 'react';

interface AudioPlayerProps {
  ws: WebSocket | null;
  useWebRTC?: boolean;  // Enable WebRTC mode
  onPlaybackStarted?: () => void;
}

export const useAudioPlayer = ({ ws, useWebRTC = true, onPlaybackStarted }: AudioPlayerProps) => {
  const [mode, setMode] = useState<'webrtc' | 'http' | 'none'>('none');
  const [isPlaying, setIsPlaying] = useState(false);
  const webrtcCheckedRef = useRef(false);
  
  // WebRTC mode: Listen for ontrack event
  useEffect(() => {
    if (!useWebRTC) return;
    
    // Check periodically for WebRTC audio element
    const checkInterval = setInterval(() => {
      const audioElement = document.querySelector('audio#webrtc-audio') as HTMLAudioElement;
      if (audioElement && audioElement.srcObject && !webrtcCheckedRef.current) {
        setMode('webrtc');
        webrtcCheckedRef.current = true;
        console.log('Using WebRTC mode');
        
        // AUTO-PLAY if track becomes ready after play button was already clicked
        audioElement.play().then(() => {
          console.log('WebRTC audio started playing automatically');
          setIsPlaying(true);
          if (onPlaybackStarted) onPlaybackStarted();
        }).catch(e => {
          console.warn('WebRTC auto-play failed (expected if no user gesture yet):', e);
        });
        
        clearInterval(checkInterval);
      }
    }, 500);
    
    return () => clearInterval(checkInterval);
  }, [useWebRTC, onPlaybackStarted]);
  
  // HTTP fallback mode: Use segment_ready events
  useEffect(() => {
    if (!ws || mode === 'webrtc') return;
    
    const handleMessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'segment_ready' && mode !== 'http') {
          setMode('http');
          console.log('Using HTTP streaming mode');
        }
      } catch (error) {
        // Ignore parse errors
      }
    };
    
    ws.addEventListener('message', handleMessage);
    return () => ws.removeEventListener('message', handleMessage);
  }, [ws, mode]);
  
  // Monitor playback state
  useEffect(() => {
    if (mode === 'webrtc') {
      const audioElement = document.querySelector('audio#webrtc-audio') as HTMLAudioElement;
      if (audioElement) {
        const handlePlay = () => {
          setIsPlaying(true);
          if (onPlaybackStarted) {
            onPlaybackStarted();
          }
        };
        const handlePause = () => setIsPlaying(false);
        
        audioElement.addEventListener('play', handlePlay);
        audioElement.addEventListener('pause', handlePause);
        audioElement.addEventListener('ended', handlePause);
        
        // Check current state
        setIsPlaying(!audioElement.paused && !audioElement.ended);
        
        return () => {
          audioElement.removeEventListener('play', handlePlay);
          audioElement.removeEventListener('pause', handlePause);
          audioElement.removeEventListener('ended', handlePause);
        };
      }
    }
  }, [mode, onPlaybackStarted]);
  
  return { isPlaying, mode };
};

