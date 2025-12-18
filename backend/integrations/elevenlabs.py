"""ElevenLabs TTS API client for DJ speech synthesis."""
import httpx
import logging
import os
from pathlib import Path
from typing import Optional
from backend.config import ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, ELEVENLABS_MODEL_ID, TTS_DIR


class ElevenLabsClient:
    """Async client for ElevenLabs TTS API."""
    
    def __init__(self):
        self.api_key = ELEVENLABS_API_KEY
        self.voice_id = ELEVENLABS_VOICE_ID
        self.model_id = ELEVENLABS_MODEL_ID
        self.base_url = "https://api.elevenlabs.io/v1"
        
        # Validate API key
        if not self.api_key:
            logging.warning("ElevenLabs API key not configured. Set ELEVENLABS_API_KEY in .env")
            self.enabled = False
        else:
            self.enabled = True
        
        self.headers = {
            "xi-api-key": self.api_key or "",
            "Content-Type": "application/json"
        }
        
        # Ensure TTS directory exists
        Path(TTS_DIR).mkdir(parents=True, exist_ok=True)
    
    async def synthesize_speech(
        self,
        text: str,
        output_filename: Optional[str] = None,
        stability: float = 0.5,
        similarity_boost: float = 0.75
    ) -> Optional[str]:
        """
        Synthesize speech from text using ElevenLabs Flash v2.5.
        
        Args:
            text: Text to synthesize
            output_filename: Optional custom filename (auto-generated if None)
            stability: Voice stability (0-1)
            similarity_boost: Voice similarity boost (0-1)
        
        Returns:
            Path to saved audio file, or None on error
        """
        if not self.enabled:
            logging.debug("ElevenLabs client disabled (missing API key)")
            return None
        
        try:
            # Generate filename if not provided
            if output_filename is None:
                import uuid
                output_filename = f"tts_{uuid.uuid4().hex[:8]}.mp3"
            
            output_path = os.path.join(TTS_DIR, output_filename)
            
            # Prepare request payload
            payload = {
                "text": text,
                "model_id": self.model_id,
                "voice_settings": {
                    "stability": stability,
                    "similarity_boost": similarity_boost
                }
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/text-to-speech/{self.voice_id}",
                    headers=self.headers,
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                
                # Save audio file
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                
                logging.info(f"TTS synthesized: {output_path}")
                return output_path
        
        except httpx.HTTPError as e:
            logging.error(f"ElevenLabs TTS error: {e}")
            if hasattr(e, 'response') and e.response:
                logging.error(f"Response: {e.response.text}")
            return None
        except Exception as e:
            logging.error(f"Unexpected TTS error: {e}")
            return None
    
    async def get_voice_info(self) -> Optional[dict]:
        """Get information about the configured voice."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/voices/{self.voice_id}",
                    headers=self.headers,
                    timeout=10.0
                )
                response.raise_for_status()
                return response.json()
        
        except httpx.HTTPError as e:
            logging.error(f"ElevenLabs voice info error: {e}")
            return None


# Global client instance
_elevenlabs_client: Optional[ElevenLabsClient] = None


def get_elevenlabs_client() -> ElevenLabsClient:
    """Get or create global ElevenLabs client."""
    global _elevenlabs_client
    if _elevenlabs_client is None:
        _elevenlabs_client = ElevenLabsClient()
    return _elevenlabs_client

