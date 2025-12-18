# Shared Contracts for AI DJ

This document defines the key shared interfaces and contract shapes utilized across the frontend and backend for consistent communication and data handling.

## WebSocket Event Types

### Client to Server
```typescript
export interface WSClientEvent {
  type: string;
  data?: any;
}

// Examples
export interface AudioChunkEvent extends WSClientEvent {
  type: 'audio_chunk';
  data: {
    audioBase64: string;
    timestamp: number;
  };
}

export interface WebRTCSignalEvent extends WSClientEvent {
  type: 'webrtc_signal';
  data: WebRTCSignalPayload;
}
```


### Server to Client
```typescript
export interface WSServerEvent {
  type: string;
  data?: any;
}

// Examples
export interface BPMDetectedEvent extends WSServerEvent {
  type: 'bpm_detected';
  data: {
    bpm: number;
    confidence: number;
  };
}

export interface AudioSegmentEvent extends WSServerEvent {
  type: 'audio_segment';
  data: AudioSegmentData;
}
```


## WebRTC Signaling Payloads

```typescript
export interface WebRTCSignalPayload {
  sdp?: RTCSessionDescriptionInit;
  candidate?: RTCIceCandidateInit;
  type: 'offer' | 'answer' | 'candidate';
  targetClientId?: string; // Who this signal is meant for
}
```


## Segment and Transition JSON Schema (Filtergraph Contract)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "AudioSegment",
  "type": "object",
  "properties": {
    "id": { "type": "string" },
    "startTime": { "type": "number" },
    "endTime": { "type": "number" },
    "effects": {
      "type": "array",
      "items": { "type": "string" }
    },
    "transitions": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "toSegmentId": { "type": "string" },
          "type": { "type": "string" },
          "duration": { "type": "number" }
        },
        "required": ["toSegmentId", "type", "duration"]
      }
    }
  },
  "required": ["id", "startTime", "endTime"]
}
```


