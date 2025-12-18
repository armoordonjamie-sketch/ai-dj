import os
import asyncio
import uuid
import logging
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ai-dj")

from backend.db import get_db, close_db
from backend.orchestration.loop import DJLoop
from backend.config import SEGMENT_DIR, SONG_CACHE_DIR

# Validate configuration on startup
from backend.config import (
    OPENROUTER_API_KEY, 
    SOUNDCHARTS_APP_ID, 
    SOUNDCHARTS_API_KEY, 
    ELEVENLABS_API_KEY
)

# Log configuration status
if not OPENROUTER_API_KEY:
    logger.warning("⚠️  OPENROUTER_API_KEY not set - LLM features will be disabled")
if not SOUNDCHARTS_APP_ID or not SOUNDCHARTS_API_KEY:
    logger.warning("⚠️  SOUNDCHARTS credentials not set - Song metadata features will be disabled")
if not ELEVENLABS_API_KEY:
    logger.warning("⚠️  ELEVENLABS_API_KEY not set - TTS features will be disabled")


# Global state
dj_loop_instance = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    global dj_loop_instance
    
    # Startup
    db = await get_db()
    print("Database connected")
    
    # Initialize DJ Loop but don't start it yet
    # It will start when play command is received via WebSocket
    dj_loop_instance = DJLoop()
    print("DJ Loop initialized (will start on play command)")
    
    yield
    
    # Shutdown
    if dj_loop_instance:
        dj_loop_instance.shutdown()
    
    await close_db()
    print("Application shutdown complete")


app = FastAPI(lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# Mount static file directories for audio streaming
# Ensure directories exist
os.makedirs(SEGMENT_DIR, exist_ok=True)
os.makedirs(SONG_CACHE_DIR, exist_ok=True)

app.mount("/audio/segments", StaticFiles(directory=SEGMENT_DIR), name="segments")
app.mount("/audio/songs", StaticFiles(directory=SONG_CACHE_DIR), name="songs")

# Health check endpoint
@app.get('/health')
async def health_check():
    return {'status': 'ok', 'service': 'ai-dj-backend'}

# Root endpoint
@app.get('/')
async def root():
    return JSONResponse(content={'message': 'Welcome to the AI DJ backend!'}, status_code=200)

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict = {}

    async def connect(self, websocket: WebSocket):
        """Accept WebSocket connection and register it."""
        try:
            await websocket.accept()
            self.active_connections[websocket] = None
            logger.info(f"WebSocket accepted: {websocket.client}")
            
            # Also register with event emitter
            from backend.orchestration.events import get_event_emitter
            emitter = get_event_emitter()
            await emitter.connect(websocket)
        except Exception as e:
            logger.error(f"Error accepting WebSocket connection: {e}")
            raise

    def disconnect(self, websocket: WebSocket):
        """Disconnect and unregister WebSocket."""
        try:
            self.active_connections.pop(websocket, None)
            # Also unregister from event emitter
            from backend.orchestration.events import get_event_emitter
            emitter = get_event_emitter()
            emitter.disconnect(websocket)
            logger.info(f"WebSocket disconnected: {websocket.client}")
        except Exception as e:
            logger.error(f"Error disconnecting WebSocket: {e}")

    async def broadcast(self, message: str):
        """Broadcast message to all active connections."""
        disconnected = []
        for connection in list(self.active_connections.keys()):
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.warning(f"Failed to send to connection: {e}")
                disconnected.append(connection)
        
        # Clean up disconnected connections
        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()

# WebSocket route
@app.websocket('/ws')
async def websocket_endpoint(websocket: WebSocket):
    """Handle WebSocket connections for real-time DJ events."""
    try:
        # Accept the connection first
        await manager.connect(websocket)
        logger.info(f"WebSocket connected: {websocket.client}")
        
        # Keep connection alive and handle messages
        while True:
            try:
                data = await websocket.receive_text()
                
                # Parse message
                try:
                    message = json.loads(data)
                    msg_type = message.get('type')
                    
                    # Handle play command
                    if msg_type == 'play':
                        logger.info("Play command received - starting DJ")
                        global dj_loop_instance
                        
                        # Debug: Log DJ loop state
                        if dj_loop_instance:
                            logger.info(f"DJ loop instance exists, running={dj_loop_instance.running}")
                        else:
                            logger.error("DJ loop instance is None!")
                        
                        # Start DJ loop if not already running
                        if dj_loop_instance and not dj_loop_instance.running:
                            logger.info("Starting DJ Loop background task")
                            try:
                                task = asyncio.create_task(dj_loop_instance.run())
                                logger.info(f"DJ Loop task created: {task}")
                            except Exception as e:
                                logger.error(f"Failed to create DJ Loop task: {e}")
                                import traceback
                                logger.error(traceback.format_exc())
                        elif dj_loop_instance and dj_loop_instance.running:
                            logger.info("DJ Loop already running, skipping")
                        
                        # Note: playback_started event is emitted by DJ loop after initialization
                    
                    elif msg_type == 'request_segments':
                        # Frontend is requesting more segments (prefetch)
                        logger.info("Segment request received from frontend")
                        if dj_loop_instance and dj_loop_instance.running:
                            # Signal DJ loop to prioritize rendering next segment
                            dj_loop_instance.request_more_segments()
                        else:
                            logger.warning("DJ loop not running, cannot provide segments")
                    
                    elif msg_type == 'segment_consumed':
                        # Frontend started playing a segment - pop from backend queue
                        if dj_loop_instance and dj_loop_instance.segment_queue:
                            try:
                                if not dj_loop_instance.segment_queue.empty():
                                    removed_item = dj_loop_instance.segment_queue.get_nowait()
                                    logger.info(f"✅ Segment consumed by frontend. Backend queue size: {dj_loop_instance.segment_queue.qsize()}")
                                else:
                                    logger.debug("segment_consumed received but backend queue already empty")
                            except Exception as e:
                                logger.error(f"Error popping from segment_queue: {e}")
                    
                    else:
                        # Handle other control messages
                        await manager.broadcast(f'Message text was: {data}')
                except json.JSONDecodeError:
                    # Legacy text message handling
                    await manager.broadcast(f'Message text was: {data}')
            except WebSocketDisconnect:
                # Client disconnected - exit loop
                logger.info("WebSocket client disconnected")
                break
            except RuntimeError as e:
                # Handle "disconnect message received" error
                if "disconnect" in str(e).lower():
                    logger.info("WebSocket disconnected (runtime error)")
                    break
                logger.error(f"WebSocket runtime error: {e}")
                break
            except Exception as e:
                # Check if it's a disconnect-related error
                error_msg = str(e).lower()
                if "disconnect" in error_msg or "closed" in error_msg:
                    logger.info(f"WebSocket connection closed: {e}")
                    break
                logger.error(f"Error processing WebSocket message: {e}")
                # Continue listening for more messages only for non-fatal errors
                continue
                
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected normally")
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket endpoint error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        try:
            manager.disconnect(websocket)
        except:
            pass

# Audio streaming endpoints with range request support
@app.get('/audio/segments/{filename}')
async def serve_segment(filename: str, request: Request):
    """Serve audio segment/mix with HTTP range request support."""
    file_path = os.path.join(SEGMENT_DIR, filename)
    
    if not os.path.exists(file_path):
        return JSONResponse(
            content={'error': 'File not found'}, 
            status_code=404
        )
    
    # Determine content type from extension
    ext = os.path.splitext(filename)[1].lower()
    content_type = 'audio/mpeg' if ext == '.mp3' else 'audio/wav'
    
    # Check for Range header
    range_header = request.headers.get('range')
    
    if range_header:
        # Parse range header (e.g., "bytes=0-1023")
        import re
        match = re.match(r'bytes=(\d+)-(\d*)', range_header)
        if match:
            start = int(match.group(1))
            end = int(match.group(2)) if match.group(2) else None
            
            file_size = os.path.getsize(file_path)
            if end is None:
                end = file_size - 1
            
            # Read requested range
            with open(file_path, 'rb') as f:
                f.seek(start)
                content = f.read(end - start + 1)
            
            return Response(
                content=content,
                status_code=206,  # Partial Content
                headers={
                    'Content-Range': f'bytes {start}-{end}/{file_size}',
                    'Accept-Ranges': 'bytes',
                    'Content-Length': str(len(content)),
                    'Content-Type': content_type,
                }
            )
    
    # No range header - serve entire file
    return FileResponse(
        file_path,
        media_type=content_type,
        headers={'Accept-Ranges': 'bytes'}
    )

# WebRTC endpoint
@app.post('/webrtc/offer')
async def webrtc_offer(request: Request):
    """Handle WebRTC SDP offer and return answer."""
    try:
        data = await request.json()
        offer_sdp = data.get('sdp')
        offer_type = data.get('type', 'offer')
        
        if not offer_sdp:
            return JSONResponse(
                content={'error': 'Missing SDP offer'},
                status_code=400
            )
        
        # Get segment queue from DJ loop
        global dj_loop_instance
        if not dj_loop_instance:
            return JSONResponse(
                content={'error': 'DJ loop not initialized'},
                status_code=503
            )
        
        # Create segment queue if it doesn't exist
        if not hasattr(dj_loop_instance, 'segment_queue') or dj_loop_instance.segment_queue is None:
            dj_loop_instance.segment_queue = asyncio.Queue()
            logger.info("WebRTC: Created segment queue for the session")
        
        # Create peer connection and get answer
        try:
            from backend.webrtc_audio import create_peer_connection
            answer_sdp, answer_type = await create_peer_connection(
                offer_sdp=offer_sdp,
                offer_type=offer_type,
                segment_queue=dj_loop_instance.segment_queue
            )
            
            return JSONResponse(content={
                'sdp': answer_sdp,
                'type': answer_type
            })
        except ImportError:
            return JSONResponse(
                content={'error': 'WebRTC not available - aiortc not installed'},
                status_code=503
            )
        except Exception as e:
            logger.error(f"WebRTC offer error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return JSONResponse(
                content={'error': f'WebRTC error: {str(e)}'},
                status_code=500
            )
    
    except Exception as e:
        logger.error(f"WebRTC endpoint error: {e}")
        return JSONResponse(
            content={'error': 'Internal server error'},
            status_code=500
        )


@app.get('/audio/songs/{filename}')
async def serve_song(filename: str, request: Request):
    """Serve song file with HTTP range request support."""
    file_path = os.path.join(SONG_CACHE_DIR, filename)
    
    if not os.path.exists(file_path):
        return JSONResponse(
            content={'error': 'File not found'}, 
            status_code=404
        )
    
    # Determine content type from extension
    ext = os.path.splitext(filename)[1].lower()
    content_type = 'audio/mpeg' if ext == '.mp3' else 'audio/wav'
    
    # Check for Range header
    range_header = request.headers.get('range')
    
    if range_header:
        import re
        match = re.match(r'bytes=(\d+)-(\d*)', range_header)
        if match:
            start = int(match.group(1))
            end = int(match.group(2)) if match.group(2) else None
            
            file_size = os.path.getsize(file_path)
            if end is None:
                end = file_size - 1
            
            with open(file_path, 'rb') as f:
                f.seek(start)
                content = f.read(end - start + 1)
            
            return Response(
                content=content,
                status_code=206,
                headers={
                    'Content-Range': f'bytes {start}-{end}/{file_size}',
                    'Accept-Ranges': 'bytes',
                    'Content-Length': str(len(content)),
                    'Content-Type': content_type,
                }
            )
    
    return FileResponse(
        file_path,
        media_type=content_type,
        headers={'Accept-Ranges': 'bytes'}
    )
