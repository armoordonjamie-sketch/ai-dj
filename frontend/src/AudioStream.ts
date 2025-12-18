import { useEffect, useRef, useState } from 'react';

interface AudioStreamProps {
  ws: WebSocket | null;
  onPlaybackStarted?: () => void;
}

// How many seconds before the end of current track to request more segments
// Segments are ~3-4 minutes, so 60 seconds gives plenty of time to fetch next
const PREFETCH_BUFFER_SECONDS = 60;
// Minimum segments to keep in queue
const MIN_QUEUE_SIZE = 2;

/**
 * Simple audio player that plays mixes from the backend.
 * The backend handles all transitions - frontend just plays the resulting audio files.
 * 
 * Features:
 * - Prefetches next segment before current one ends for seamless playback
 * - Preloads audio files in the queue
 * - Requests more segments when queue runs low
 */
export const useAudioStream = ({ ws, onPlaybackStarted }: AudioStreamProps) => {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioQueueRef = useRef<string[]>([]);
  const preloadedAudioRef = useRef<HTMLAudioElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const isPlayingRef = useRef(false);
  const currentUrlRef = useRef<string | null>(null);
  const retryCountRef = useRef(0);
  const hasRequestedMoreRef = useRef(false);
  const MAX_RETRIES = 2;

  useEffect(() => {
    if (!ws) return;

    const playNext = (overlap = false) => {
      if (audioQueueRef.current.length === 0) {
        console.log('🎵 Queue empty, waiting for more audio');
        // Only stop if we really have nothing left and are not overlapping
        if (!overlap) {
          isPlayingRef.current = false;
          setIsPlaying(false);
        }
        return;
      }

      const nextUrl = audioQueueRef.current.shift();
      if (!nextUrl) return;

      currentUrlRef.current = nextUrl;
      retryCountRef.current = 0;

      console.log(`🎵 Playing (queue size: ${audioQueueRef.current.length}):`, nextUrl);

      playUrl(nextUrl, overlap);
    };

    // Request more segments from backend if queue is low
    const requestMoreSegments = () => {
      if (ws && ws.readyState === WebSocket.OPEN && !hasRequestedMoreRef.current) {
        hasRequestedMoreRef.current = true;
        console.log('📡 Requesting more segments from backend...');
        ws.send(JSON.stringify({ type: 'request_segments' }));
        // Reset flag after 10 seconds to allow future requests
        setTimeout(() => {
          hasRequestedMoreRef.current = false;
        }, 10000);
      }
    };

    // Preload the next audio in queue
    const preloadNext = () => {
      if (audioQueueRef.current.length > 0 && !preloadedAudioRef.current) {
        const nextUrl = audioQueueRef.current[0];
        console.log('🔄 Preloading next segment:', nextUrl);
        const preloadAudio = new Audio();
        preloadAudio.preload = 'auto';
        preloadAudio.src = nextUrl;
        preloadedAudioRef.current = preloadAudio;
      }
    };

    const playUrl = (url: string, overlap = false) => {
      // Store reference to old audio to clean it up
      const oldAudio = audioRef.current;

      // If NOT overlapping, clean up immediately
      if (oldAudio && !overlap) {
        oldAudio.pause();
        oldAudio.src = '';
        oldAudio.onloadeddata = null;
        oldAudio.oncanplaythrough = null;
        oldAudio.onended = null;
        oldAudio.onerror = null;
        oldAudio.onplay = null;
        oldAudio.ontimeupdate = null;
      } else if (oldAudio && overlap) {
        // If overlapping, let old audio finish naturally (it's near end anyway)
        // Just remove listeners so it doesn't trigger onended again
        oldAudio.onended = null;
        oldAudio.ontimeupdate = null;
      }

      // Check if we have this URL preloaded
      let audio: HTMLAudioElement;
      let isPreloaded = false;
      if (preloadedAudioRef.current && preloadedAudioRef.current.src === url) {
        console.log('🚀 Using preloaded audio:', url);
        audio = preloadedAudioRef.current;
        preloadedAudioRef.current = null;
        isPreloaded = true;
      } else {
        // Create new audio element
        audio = new Audio(url);
      }

      audio.volume = 0.8;
      audio.preload = 'auto';
      audioRef.current = audio;

      audio.onplay = () => {
        console.log('▶️ Audio playback STARTED');
        setIsPlaying(true);
        isPlayingRef.current = true;

        // Signal to backend that a segment has been consumed (for queue management)
        if (ws && ws.readyState === WebSocket.OPEN) {
          console.log('📡 Signaling segment consumption to backend');
          ws.send(JSON.stringify({ type: 'segment_consumed', url: url }));
        }

        if (onPlaybackStarted) {
          onPlaybackStarted();
        }
      };

      // We'll use a local flag for the transition to avoid closure staleness
      let transitionStarted = false;
      let hasPreloaded = false;
      let hasRequestedMore = false;

      audio.ontimeupdate = () => {
        const remaining = audio.duration - audio.currentTime;

        // Prefetch logic (start preloading when near end)
        if (remaining <= PREFETCH_BUFFER_SECONDS && !hasPreloaded) {
          hasPreloaded = true;
          preloadNext();

          // If queue is getting low, request more segments from backend
          if (audioQueueRef.current.length < MIN_QUEUE_SIZE && !hasRequestedMore) {
            hasRequestedMore = true;
            requestMoreSegments();
          }
        }

        // Gapless transition: Start next track slightly before current one ends (0.2s overlap)
        if (remaining <= 0.2 && !transitionStarted && audioQueueRef.current.length > 0) {
          console.log('⚡ Starting gapless transition...');
          transitionStarted = true;
          playNext(true); // true = overlap (don't kill current immediately)
        }
      };

      audio.onended = () => {
        if (!transitionStarted) {
          console.log('🎵 Audio ended naturally (no overlap triggered), playing next');
          playNext(false);
        } else {
          console.log('🎵 Audio finished (overlap was already triggered)');
        }
      };

      audio.onerror = () => {
        const errorCode = audio.error?.code;
        const errorMessage = audio.error?.message || 'Unknown error';
        console.error(`❌ Audio error (code ${errorCode}): ${errorMessage}`, url);
        handleError(url);
      };

      // For preloaded audio, start playback immediately since it's already loaded
      if (isPreloaded && audio.readyState >= 3) {
        console.log(`🎵 Preloaded audio ready (duration: ${audio.duration.toFixed(1)}s), starting immediately`);
        startPlayback(audio);
      } else {
        // For non-preloaded audio, wait for it to load
        audio.oncanplaythrough = () => {
          console.log(`🎵 Audio ready to play through:`, url);
          startPlayback(audio);
        };

        audio.onloadeddata = () => {
          console.log(`🎵 Audio loaded (duration: ${audio.duration.toFixed(1)}s, readyState: ${audio.readyState}):`, url);
          // readyState 4 = HAVE_ENOUGH_DATA
          if (audio.readyState >= 3) {
            startPlayback(audio);
          }
        };
      }
    };

    const startPlayback = (audio: HTMLAudioElement) => {
      if (audio.paused) {
        console.log('🎵 Attempting to play audio...');
        const playPromise = audio.play();

        if (playPromise !== undefined) {
          playPromise.then(() => {
            console.log('✅ Play promise resolved');
          }).catch((e) => {
            console.error('❌ Failed to play audio:', e.name, e.message);
            // If autoplay was blocked, we need user interaction
            if (e.name === 'NotAllowedError') {
              console.log('⚠️ Autoplay blocked - waiting for user interaction');
              // Don't retry, just wait - the user needs to interact with the page
            } else {
              handleError(audio.src);
            }
          });
        }
      }
    };

    const handleError = (url: string) => {
      retryCountRef.current++;

      if (retryCountRef.current <= MAX_RETRIES) {
        // Retry after a short delay (file might still be rendering)
        console.log(`🔄 Retrying (${retryCountRef.current}/${MAX_RETRIES}) in 1s...`);
        setTimeout(() => {
          if (currentUrlRef.current === url) {
            playUrl(url);
          }
        }, 1000);
      } else {
        console.log('⏭️ Max retries reached, skipping to next');
        playNext(false);
      }
    };

    const handleMessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);

        // Only handle segment_ready events (playback_started is deprecated)
        if (data.type === 'segment_ready') {
          const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

          const url = data.data?.segment_url;
          if (url) {
            const fullUrl = `${apiUrl}${url}`;

            // Prevent duplicate URLs in queue
            if (audioQueueRef.current.includes(fullUrl)) {
              console.log('🎵 Skipping duplicate:', fullUrl);
              return;
            }

            console.log(`🎵 Segment queued (queue size: ${audioQueueRef.current.length + 1}):`, fullUrl);

            // Add to queue
            audioQueueRef.current.push(fullUrl);

            // Immediately preload the first queued item if we're playing
            if (isPlayingRef.current && audioQueueRef.current.length === 1) {
              preloadNext();
            }

            // If not currently playing, start
            if (!isPlayingRef.current) {
              console.log('🎵 Starting playback from queue');
              playNext(false);
            }
          }
        }
      } catch (error) {
        console.error('Error handling WebSocket message:', error);
      }
    };

    ws.addEventListener('message', handleMessage);

    return () => {
      ws.removeEventListener('message', handleMessage);
    };
  }, [ws, onPlaybackStarted]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.src = '';
        audioRef.current = null;
      }
      if (preloadedAudioRef.current) {
        preloadedAudioRef.current.src = '';
        preloadedAudioRef.current = null;
      }
      audioQueueRef.current = [];
    };
  }, []);

  return { isPlaying };
};

export default useAudioStream;
