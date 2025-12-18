"""WebRTC audio track implementation for streaming DJ segments."""
import asyncio
import logging
import os
from typing import Optional
import numpy as np
import av

# Create logger for this module
logger = logging.getLogger("ai-dj.webrtc")

try:
    from aiortc import AudioStreamTrack, RTCSessionDescription
    from aiortc.contrib.media import MediaPlayer
    AIORTC_AVAILABLE = True
except ImportError:
    AIORTC_AVAILABLE = False
    logger.warning("aiortc not installed - WebRTC features will be disabled")


class DJAudioTrack(AudioStreamTrack):
    """
    Custom AudioStreamTrack that consumes PCM audio from segment queue.
    """
    
    def __init__(self, segment_queue: asyncio.Queue):
        if not AIORTC_AVAILABLE:
            raise ImportError("aiortc is required for WebRTC audio streaming")
        
        super().__init__()
        self.segment_queue = segment_queue
        self.current_container: Optional[av.container.InputContainer] = None
        self.frame_generator = None
        self.frame_index = 0
        self.running = True
        
        # Audio format: 48kHz, stereo, 16-bit PCM
        self.sample_rate = 48000
        self.channels = 2
        
        # Pre-generate a silence frame to save time
        self.SAMPLES_PER_FRAME = 960  # 20ms at 48kHz
        self._silence_samples = np.zeros((self.SAMPLES_PER_FRAME, self.channels), dtype=np.int16)
        
        logger.info("WebRTC Track: Initialized")

    async def recv(self):
        """
        Receive next audio frame for WebRTC streaming.
        """
        if not AIORTC_AVAILABLE:
            raise RuntimeError("aiortc not available")
        
        # Heartbeat log every 500 frames (~10 seconds)
        if self.frame_index % 500 == 0:
            qsize = self.segment_queue.qsize() if self.segment_queue else 0
            logger.debug(f"WebRTC Track: Heartbeat (frame={self.frame_index}, queue={qsize})")

        # 1. Try to get frame from current segment generator
        if self.frame_generator:
            try:
                frame = next(self.frame_generator)
                if frame is not None:
                    # Resample/Reformat if needed
                    if frame.sample_rate != self.sample_rate or \
                       frame.layout.name != 'stereo' or \
                       frame.format.name != 's16':
                        
                        resampler = av.AudioResampler(
                            format='s16',
                            layout='stereo',
                            rate=self.sample_rate
                        )
                        frame = resampler.resample(frame)[0]
                    
                    # Force continuous PTS
                    frame.pts = self.frame_index * self.SAMPLES_PER_FRAME
                    frame.time_base = av.Rational(1, self.sample_rate)
                    self.frame_index += 1
                    return frame
            except StopIteration:
                logger.info("WebRTC: Finished current segment")
                self._close_current_segment()
            except Exception as e:
                logger.error(f"WebRTC: Error reading frame from generator: {e}")
                self._close_current_segment()
        
        # 2. No generator active, check queue for new segment
        try:
            if not self.segment_queue.empty():
                segment_path = self.segment_queue.get_nowait()
                if segment_path and os.path.exists(segment_path):
                    logger.info(f"WebRTC: [Queue Match] Loading next segment: {segment_path}")
                    self._load_segment(segment_path)
                    # Recursively call recv to get first frame from new generator
                    return await self.recv()
                else:
                    logger.warning(f"WebRTC: Segment path does not exist: {segment_path}")
        except Exception as e:
            logger.error(f"WebRTC: Queue retrieval error: {e}")
        
        # 3. Default: Return silence
        return self._generate_silence_frame()

    def _load_segment(self, segment_path: str):
        """Load a new audio segment and create its frame generator."""
        try:
            self._close_current_segment()
            container = av.open(segment_path)
            # Find the first audio stream
            audio_stream = next((s for s in container.streams if s.type == 'audio'), None)
            if not audio_stream:
                logger.error(f"WebRTC: No audio stream found in {segment_path}")
                container.close()
                return
                
            self.current_container = container
            self.frame_generator = container.decode(audio_stream)
            logger.info(f"WebRTC: Decoder ready for {os.path.basename(segment_path)}")
        except Exception as e:
            logger.error(f"WebRTC: Failed to load segment {segment_path}: {e}")
            self._close_current_segment()

    def _close_current_segment(self):
        """Close current audio segment and clear generator."""
        self.frame_generator = None
        if self.current_container:
            try:
                self.current_container.close()
            except Exception:
                pass
            self.current_container = None

    def _generate_silence_frame(self):
        """Generate a silence frame."""
        frame = av.AudioFrame.from_ndarray(self._silence_samples, format='s16', layout='stereo')
        frame.sample_rate = self.sample_rate
        frame.pts = self.frame_index * self.SAMPLES_PER_FRAME
        frame.time_base = av.Rational(1, self.sample_rate)
        self.frame_index += 1
        return frame

    def stop(self):
        """Stop the track and clean up resources."""
        self.running = False
        self._close_current_segment()


# Global WebRTC peer connections (for cleanup)
_peer_connections: dict = {}


async def create_peer_connection(offer_sdp: str, offer_type: str, segment_queue: asyncio.Queue) -> tuple:
    """
    Create WebRTC peer connection and return answer SDP.
    """
    if not AIORTC_AVAILABLE:
        raise ImportError("aiortc is required for WebRTC")
    
    from aiortc import RTCPeerConnection, RTCSessionDescription
    
    # Create peer connection
    pc = RTCPeerConnection()
    
    # Add audio track
    audio_track = DJAudioTrack(segment_queue)
    pc.addTrack(audio_track)
    
    # Set remote description (offer)
    offer = RTCSessionDescription(sdp=offer_sdp, type=offer_type)
    await pc.setRemoteDescription(offer)
    
    # Create answer
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    
    # Store peer connection
    connection_id = id(pc)
    _peer_connections[connection_id] = pc
    
    return answer.sdp, answer.type
