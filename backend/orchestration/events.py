"""WebSocket event emitting helpers for AI DJ orchestration."""
import json
import asyncio
from fastapi import WebSocket
from typing import Optional

class WebSocketEventEmitter:
    def __init__(self):
        self.connections = set()

    async def connect(self, websocket: WebSocket):
        """Register a websocket connection (assumes it's already accepted)."""
        self.connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.connections.discard(websocket)

    async def emit(self, event_type: str, data: dict):
        if not self.connections:
            return
        message = json.dumps({"type": event_type, "data": data})
        coros = [conn.send_text(message) for conn in self.connections]
        await asyncio.gather(*coros, return_exceptions=True)

    async def broadcast_now_playing(self, now_playing_data: dict):
        await self.emit("now_playing", now_playing_data)

    async def broadcast_decision_trace(self, trace_data: dict):
        await self.emit("decision_trace", trace_data)


# Global event emitter instance
_event_emitter: Optional[WebSocketEventEmitter] = None


def get_event_emitter() -> WebSocketEventEmitter:
    """Get or create global event emitter instance."""
    global _event_emitter
    if _event_emitter is None:
        _event_emitter = WebSocketEventEmitter()
    return _event_emitter


