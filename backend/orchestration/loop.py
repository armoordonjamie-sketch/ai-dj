"""Background DJ loop management for AI DJ planning and playback."""
import asyncio
import logging
import uuid
import os

# Create logger for this module
logger = logging.getLogger("ai-dj.loop")

from backend.orchestration.graph import create_initialization_graph, create_planning_graph
from backend.db import get_db


class DJLoop:
    def __init__(self):
        self.init_graph = create_initialization_graph()
        self.planning_graph = create_planning_graph()
        self.running = False
        self.session_id = str(uuid.uuid4())
        self.min_segments = 2  # Keep at least 2 segments ahead
        self.max_segments = 5  # Allow more pre-rendered segments
        self.initial_song_loaded = False
        self.segments_planned = 0  # Track total segments planned
        self.segments_rendered = []  # Track rendered segment paths
        # WebRTC segment queue (created in run() when event loop exists)
        self.segment_queue = None
        # Flag to prioritize rendering when frontend requests more
        self._urgent_segment_needed = False
    
    def request_more_segments(self):
        """Signal that frontend needs more segments urgently."""
        logger.info("📡 Frontend requested more segments - setting urgent flag")
        self._urgent_segment_needed = True
        
    async def run(self):
        """Main DJ loop - manages segment queue and triggers planning."""
        logger.info("🎵 DJ Loop run() method started")
        
        if self.init_graph is None or self.planning_graph is None:
            logger.error("DJLoop: No graphs available - LangGraph may not be installed properly")
            return
        
        # Ensure segment queue exists but DON'T overwrite if main.py already created it
        if self.segment_queue is None:
            self.segment_queue = asyncio.Queue()
            logger.info("Created new segment queue")
        else:
            logger.info("Using existing segment queue")
        
        # Create session in database
        try:
            db = await get_db()
            await db.create_session(self.session_id, mode="autonomous")
            logger.info(f"Created DJ session: {self.session_id}")
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
        
        self.running = True
        
        # Step 1: Run initialization graph to get first song
        while not self.initial_song_loaded and self.running:
            logger.info("Running initialization graph to select and download initial song")
            try:
                init_state = {
                    "now_playing": [],
                    "decision_trace": [],
                    "session_id": self.session_id
                }
                
                init_result = await self.init_graph.ainvoke(init_state)
                
                if init_result.get("selected_song_uuid") and init_result.get("rendered_segment_path"):
                    # The init graph already rendered the intro segment with TTS
                    # and emitted segment_ready via EmitEventsNode
                    rendered_path = init_result["rendered_segment_path"]
                    logger.info(f"Initial song with TTS intro rendered: {rendered_path}")
                    
                    self.initial_song_loaded = True
                    
                    # Add the rendered intro segment to the queue
                    if self.segment_queue:
                        await self.segment_queue.put(rendered_path)
                        self.segments_rendered.append(rendered_path)
                        self.segments_planned += 1
                        logger.info(f"Added intro segment to queue (queue size: {self.segment_queue.qsize()})")
                    
                    # Record initial song play in database
                    try:
                        from datetime import datetime
                        await db.insert_play_history({
                            'session_id': self.session_id,
                            'song_uuid': init_result["selected_song_uuid"],
                            'started_at': datetime.utcnow().isoformat(),
                            'transition_type': 'initial'
                        })
                        logger.info(f"Recorded initial song: {init_result['selected_song_uuid']}")
                    except Exception as e:
                        logger.error(f"Failed to record initial play: {e}")
                    
                    break # Success!
                elif init_result.get("selected_song_uuid"):
                    # Song was selected but rendering failed - log details
                    logger.error(f"Initialization incomplete - song selected but no rendered segment")
                    logger.error(f"  selected_song_uuid: {init_result.get('selected_song_uuid')}")
                    logger.error(f"  song_b_path: {init_result.get('song_b_path')}")
                    logger.error(f"  rendered_segment_path: {init_result.get('rendered_segment_path')}")
                    logger.error(f"  download_status: {init_result.get('download_status')}")
                    await asyncio.sleep(30)
                else:
                    logger.error("Initialization failed - no song selected")
                    logger.error(f"  download_status: {init_result.get('download_status')}")
                    await asyncio.sleep(30)
            except Exception as e:
                logger.error(f"Initialization graph error: {e}")
                import traceback
                logger.error(traceback.format_exc())
                await asyncio.sleep(30)
        
        # Step 2: Run planning graph continuously while playing
        # Start planning immediately after initial song loads
        last_planning_time = -999  # Negative to trigger immediately
        planning_cooldown = 5  # Reduced to 5 seconds for faster planning
        
        while self.running:
            try:
                current_time = asyncio.get_event_loop().time()
                
                # Trigger planning if enough time has passed since last planning
                # OR if the frontend urgently needs segments
                is_urgent = self._urgent_segment_needed
                can_plan = (current_time - last_planning_time) >= planning_cooldown or is_urgent
                
                # Check queue size if it exists, but bypass if urgent
                if can_plan and self.segment_queue and not is_urgent:
                    q_size = self.segment_queue.qsize()
                    if q_size >= 3:  # Allow a small buffer of 3 segments
                        logger.info(f"Queue has {q_size} segments - skipping planning to avoid spam")
                        can_plan = False
                
                if can_plan:
                    if is_urgent:
                        logger.info("⚡ Planning because frontend requested segments")
                    self._urgent_segment_needed = False
                    
                    # Get recent plays to find the current song (song_a for planning)
                    db = await get_db()
                    history = await db.get_recent_plays(self.session_id, limit=10)
                    
                    # Log current state for debugging
                    logger.info(f"Loop iteration: segments_planned={self.segments_planned}")
                    
                    # Don't cap - just keep planning. Each segment takes ~20s to render
                    # and ~3min to play, so we naturally won't get too far ahead.
                    # The frontend will request segments as needed.
                    
                    # New segment needed - plan it
                    logger.info(f"Planning new segment (segments rendered: {len(self.segments_rendered)})")
                    last_planning_time = current_time
                    
                    # Determine song_a from most recent segment or play history
                    song_a_uuid = None
                    if self.segments_rendered and len(self.segments_rendered) > 0:
                        # Use the last rendered segment's song as song_a
                        # (We need to track this in segment metadata)
                        pass
                    
                    if history and len(history) > 0:
                        # Use most recent play as song_a
                        song_a_uuid = history[0].get('song_uuid')
                    
                    logger.info(f"Planning segment #{self.segments_planned + 1} from song_a={song_a_uuid}")
                    
                    # Trigger planning graph
                    state = {
                        "now_playing": [],
                        "decision_trace": [],
                        "session_id": self.session_id,
                        "song_a_uuid": song_a_uuid
                    }
                    
                    try:
                        logger.info(f"Invoking planning graph with state: song_a_uuid={song_a_uuid}, session_id={self.session_id}")
                        result = await self.planning_graph.ainvoke(state)
                        logger.info(f"Planning graph execution completed. Result keys: {list(result.keys())}")
                        
                        # Segment is emitted via WebSocket in EmitEventsNode
                        # No need to queue it here - frontend will handle it
                        rendered_path = result.get("rendered_segment_path")
                        selected_uuid = result.get("selected_song_uuid")
                        
                        logger.info(f"Planning result: rendered_path={rendered_path}, selected_uuid={selected_uuid}")
                        
                        if rendered_path and os.path.exists(rendered_path):
                            logger.info(f"✅ Segment #{self.segments_planned + 1} rendered successfully: {rendered_path}")
                            
                            # Add segment to WebRTC queue
                            try:
                                await self.segment_queue.put(rendered_path)
                                self.segments_rendered.append(rendered_path)
                                self.segments_planned += 1
                                logger.info(f"Added segment to WebRTC queue (queue size now: {self.segment_queue.qsize()})")
                            except Exception as e:
                                logger.error(f"Failed to add segment to queue: {e}")
                            
                            # Continue planning more segments quickly
                            planning_cooldown = 3  # Very short cooldown to plan next segment
                            logger.info(f"Segment {self.segments_planned} complete, will plan next in {planning_cooldown}s")
                        else:
                            logger.warning(f"⚠️ Planning completed but no segment rendered. rendered_path={rendered_path}, selected_uuid={selected_uuid}")
                            if rendered_path:
                                logger.warning(f"Segment path exists check: {os.path.exists(rendered_path)}")
                        
                        # If planning failed, increase cooldown
                        if not selected_uuid:
                            logger.warning("Planning failed - no song selected, increasing cooldown")
                            planning_cooldown = min(120, planning_cooldown * 1.5)
                            
                    except Exception as e:
                        logger.error(f"Planning graph execution error: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                        planning_cooldown = min(120, planning_cooldown * 1.5)
                
                else:
                    # Not time to plan yet
                    time_until_planning = planning_cooldown - (current_time - last_planning_time)
                    logger.debug(f"Planning cooldown active: {time_until_planning:.1f}s remaining")
                
                await asyncio.sleep(2)  # Check every 2 seconds for more responsiveness
                
            except Exception as e:
                logger.error(f"Error in DJLoop: {e}")
                import traceback
                logger.error(traceback.format_exc())
                await asyncio.sleep(5)
    
    def shutdown(self):
        """Shutdown the DJ loop."""
        self.running = False
        logging.info("DJ Loop shutdown requested")
