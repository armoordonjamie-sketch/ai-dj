import { useEffect, useRef } from 'react';

let globalAudioElement: HTMLAudioElement | null = null;

// Export function to start audio playback (called after user interaction)
export const startAudioPlayback = async () => {
  if (globalAudioElement) {
    try {
      console.log('Attempting to start audio playback');
      await globalAudioElement.play();
      console.log('Audio playback started successfully');
      return true;
    } catch (e) {
      console.error('Failed to start audio:', e);
      return false;
    }
  }
  console.log('No audio element to play');
  return false;
};

const logWebRTCState = (peerConnection: RTCPeerConnection | null, context: string) => {
  if (!peerConnection) {
    console.log(`[WebRTC State] ${context}: peerConnection is null`);
  } else {
    console.log(`[WebRTC State] ${context}: signalingState=${peerConnection.signalingState}, connectionState=${peerConnection.connectionState}, iceConnectionState=${peerConnection.iceConnectionState}`);
  }
};

const useWebRTC = (onTrackReady?: (audioElement: HTMLAudioElement) => void) => {
  const peerConnectionRef = useRef<RTCPeerConnection | null>(null);

  useEffect(() => {
    // Don't create a new connection if one exists and state is not closed
    if (peerConnectionRef.current && peerConnectionRef.current.connectionState !== 'closed') {
      console.log('WebRTC already initialized, skipping');
      return;
    }

    let peerConnection: RTCPeerConnection | null = new RTCPeerConnection({
      iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
    });
    peerConnectionRef.current = peerConnection;

    logWebRTCState(peerConnection, 'initialization');

    peerConnection.onconnectionstatechange = () => {
      logWebRTCState(peerConnection, 'onconnectionstatechange');
      if (peerConnection.connectionState === 'failed' || peerConnection.connectionState === 'closed') {
        console.log('Closing and cleaning up failed/closed WebRTC connection');
        peerConnection.close();
        peerConnectionRef.current = null;
      }
    };

    peerConnection.oniceconnectionstatechange = () => {
      logWebRTCState(peerConnection, 'oniceconnectionstatechange');
    };

    peerConnection.onicegatheringstatechange = () => {
      logWebRTCState(peerConnection, 'onicegatheringstatechange');
    };

    peerConnection.ontrack = (event) => {
      console.log('Received remote track:', event.track.kind);
      const remoteStream = new MediaStream([event.track]);

      // Find or create audio element
      let audioElement = document.querySelector('audio#webrtc-audio') as HTMLAudioElement;
      if (!audioElement) {
        audioElement = document.createElement('audio');
        audioElement.id = 'webrtc-audio';
        audioElement.autoplay = false; // Wait for user interaction
        audioElement.volume = 0.8;
        document.body.appendChild(audioElement);
      }

      audioElement.srcObject = remoteStream;
      globalAudioElement = audioElement;

      // Try to autoplay since the user already gave a gesture by clicking "Play DJ"
      audioElement.play().then(() => {
        console.log('WebRTC track auto-started on arrival');
      }).catch(e => {
        console.log('WebRTC track received - waiting for play command');
      });

      // Notify that track is ready
      if (onTrackReady) {
        onTrackReady(audioElement);
      }
    };

    const setupWebRTC = async () => {
      try {
        logWebRTCState(peerConnection, 'setupWebRTC:start');

        // Create offer
        const offer = await peerConnection.createOffer({
          offerToReceiveAudio: true,
          offerToReceiveVideo: false
        });
        logWebRTCState(peerConnection, 'setupWebRTC:offerCreated');

        await peerConnection.setLocalDescription(offer);

        // Send offer to backend
        const apiUrl = (import.meta as any).env.VITE_API_URL || 'http://localhost:8000';
        const response = await fetch(`${apiUrl}/webrtc/offer`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ sdp: offer.sdp, type: offer.type })
        });

        if (!response.ok) {
          throw new Error(`WebRTC offer failed: ${response.statusText}`);
        }

        const answer = await response.json();
        logWebRTCState(peerConnection, 'setupWebRTC:answerReceived');

        // Before setting remote description, confirm connection state
        logWebRTCState(peerConnection, 'setupWebRTC:beforeSetRemoteDescription');

        if (peerConnection.signalingState === 'closed') {
          throw new Error('Peer connection is already closed before setting remote description');
        }

        await peerConnection.setRemoteDescription(new RTCSessionDescription({ sdp: answer.sdp, type: answer.type }));
        logWebRTCState(peerConnection, 'setupWebRTC:remoteDescriptionSet');

        console.log('WebRTC connection established');
      } catch (error) {
        console.error('WebRTC setup error:', error);
      }
    };

    setupWebRTC();

    return () => {
      if (peerConnectionRef.current && peerConnectionRef.current.connectionState !== 'closed') {
        console.log('Cleaning up WebRTC connection');
        peerConnectionRef.current.close();
      }
    };
  }, []);
};

export default useWebRTC;
