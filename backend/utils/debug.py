import os
import subprocess
import logging
import asyncio
from backend.db import get_db
from backend.orchestration.graph import create_planning_graph
from backend.config import SEGMENT_DIR

logger = logging.getLogger("ai-dj.debug")

async def debug_stitch_first_4_songs():
    """
    Debug helper to run the actual AI pipeline for the first 4 cached songs
    and save the resulting rendered segments to a single MP3.
    """
    try:
        db = await get_db()
        # Get 4 songs to demo
        songs = await db.get_cached_songs(limit=4)
        
        if len(songs) < 2:
            logger.warning(f"Not enough cached songs to create a demo mix (found {len(songs)}, need at least 2).")
            return
        
        planning_graph = create_planning_graph()
        if not planning_graph:
            logger.error("Could not create planning graph for debug stitch.")
            return

        rendered_segments = []
        session_id = "debug-stitch-session"
        
        logger.info(f"🚀 Starting debug AI mix generation for {len(songs)} songs...")

        # Process each song transition
        for i in range(len(songs) - 1):
            song_a = songs[i]
            song_b = songs[i+1]
            
            logger.info(f"Mixing {i+1}: {song_a['title']} -> {song_b['title']}")
            
            # Use actual offsets to hear transitions correctly
            # We'll transition from 30s before the end of song A
            duration_a = song_a.get('duration_sec', 180)
            offset_a = max(0, duration_a - 40)
            
            state = {
                "session_id": session_id,
                "song_a_uuid": song_a['uuid'],
                "song_a_path": song_a['local_path'],
                "song_b_uuid": song_b['uuid'],
                "song_b_path": song_b['local_path'],
                "selected_song_uuid": song_b['uuid'],
                "decision_trace": [],
                "now_playing": [],
                "segment_cursor": {
                    "song_uuid": song_a['uuid'],
                    "song_offset_sec": offset_a,
                    "segment_index": i
                }
            }
            
            # Run the actual AI pipeline
            try:
                result = await planning_graph.ainvoke(state)
                segment_path = result.get("rendered_segment_path")
                
                if segment_path and os.path.exists(segment_path):
                    rendered_segments.append(segment_path)
                    logger.info(f"✅ Rendered segment for transition {i+1}: {segment_path}")
                else:
                    logger.warning(f"⚠️ Failed to render segment for transition {i+1}")
            except Exception as e:
                logger.error(f"Error in AI pipeline for transition {i+1}: {e}")

        if not rendered_segments:
            logger.warning("No segments were successfully rendered.")
            return

        # Stitch the resulting AI-rendered segments together
        output_path = "data/debug_stitch_ai.mp3"
        
        # Use simple concat protocol since we've forced output formats in renderer
        list_path = "data/segments_list.txt"
        with open(list_path, 'w') as f:
            for seg in rendered_segments:
                f.write(f"file '{os.path.abspath(seg)}'\n")
        
        cmd = [
            'ffmpeg', '-y', 
            '-f', 'concat', 
            '-safe', '0', 
            '-i', list_path, 
            '-c:a', 'libmp3lame', 
            '-q:a', '2', 
            output_path
        ]
        
        logger.info(f"Stitching {len(rendered_segments)} AI segments into {output_path}...")
        
        process = subprocess.run(cmd, capture_output=True, text=True)
        
        if process.returncode == 0:
            logger.info(f"✨ SUCCESS! AI demo mix saved to {output_path}")
            logger.info("The file now contains actual transitions and DJ talk.")
        else:
            logger.error(f"FFmpeg failed to stitch segments: {process.stderr}")
            
    except Exception as e:
        logger.error(f"Error in debug_stitch_first_4_songs: {e}")
        import traceback
        logger.error(traceback.format_exc())
