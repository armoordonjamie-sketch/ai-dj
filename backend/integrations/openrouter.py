"""OpenRouter API client for Gemini 2.5 Flash LLM calls."""
import httpx
import json
import logging
from typing import Optional, Dict, Any, List
from backend.config import OPENROUTER_API_KEY


class OpenRouterClient:
    """Async client for OpenRouter API (Gemini 2.5 Flash)."""
    
    def __init__(self):
        self.api_key = OPENROUTER_API_KEY
        self.base_url = "https://openrouter.ai/api/v1"
        self.model = "google/gemini-2.5-flash"
        
        # Validate API key
        if not self.api_key:
            logging.warning("OpenRouter API key not configured. Set OPENROUTER_API_KEY in .env")
            self.enabled = False
        else:
            self.enabled = True
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key or ''}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://ai-dj.local",
            "X-Title": "AI DJ"
        }
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        thinking_budget: Optional[int] = None,
        json_mode: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Call Gemini 2.5 Flash via OpenRouter.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-1)
            max_tokens: Max tokens to generate
            thinking_budget: Max tokens for reasoning (Gemini 2.5 feature)
            json_mode: Enable JSON response format
        
        Returns:
            Response dict with 'content' and metadata, or None on error
        """
        if not self.enabled:
            logging.debug("OpenRouter client disabled (missing API key)")
            return None
        
        try:
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature
            }
            
            if max_tokens:
                payload["max_tokens"] = max_tokens
            
            # Gemini 2.5 thinking budget parameter
            if thinking_budget:
                payload["max_reasoning_tokens"] = thinking_budget
            
            # JSON mode
            if json_mode:
                payload["response_format"] = {"type": "json_object"}
                # Add JSON instruction to system message
                if messages and messages[0]["role"] == "system":
                    messages[0]["content"] += "\n\nRespond with valid JSON only."
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload,
                    timeout=60.0
                )
                response.raise_for_status()
                data = response.json()
                
                # Extract response
                if data.get('choices') and len(data['choices']) > 0:
                    choice = data['choices'][0]
                    content = choice.get('message', {}).get('content', '')
                    
                    result = {
                        'content': content,
                        'model': data.get('model'),
                        'usage': data.get('usage', {}),
                        'finish_reason': choice.get('finish_reason')
                    }
                    
                    # Parse JSON if requested
                    if json_mode:
                        try:
                            result['parsed'] = json.loads(content)
                        except json.JSONDecodeError as e:
                            logging.error(f"Failed to parse JSON response: {e}")
                            result['parsed'] = None
                    
                    return result
                
                logging.error(f"No choices in OpenRouter response: {data}")
                return None
        
        except httpx.HTTPError as e:
            logging.error(f"OpenRouter API error: {e}")
            if hasattr(e, 'response') and e.response:
                logging.error(f"Response body: {e.response.text}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error in OpenRouter call: {e}")
            return None
    
    async def generate_track_selection(
        self,
        user_controls: Dict[str, Any],
        session_history: List[Dict[str, Any]],
        global_history: List[Dict[str, Any]],
        available_songs: List[Dict[str, Any]],
        thinking_budget: int = 2000
    ) -> Optional[Dict[str, Any]]:
        """
        Generate track selection decision.
        
        Args:
            user_controls: User preferences (mood, genre, prompt)
            session_history: Recent play history for current session
            global_history: Recent play history across all sessions
            available_songs: Candidate songs with metadata
            thinking_budget: Reasoning token budget
        
        Returns:
            Dict with selected song UUID and rationale
        """
        system_prompt = """You are an expert DJ selecting tracks for continuous flow.

SELECTION CRITERIA (in priority order):
1. Musical compatibility: tempo (±5 BPM for blends, ±10+ for cuts), key compatibility (Camelot wheel), energy curve
2. Lyrical coherence: themes, moods, narrative continuity from previous tracks
3. User personalization: respect mood slider, genre preferences, freeform prompts
4. Transition variety: avoid repetitive transition types (if last 3 were blends, consider a cut/echo-out)
5. Emotional arc: build tension/release over 3-4 tracks, manage energy intentionally
6. Recency guardrails: avoid songs appearing in recent session/global history unless no fresh option remains.

Use Soundcharts audio features:
- tempo: BPM for beatmatching and transition selection
- key: harmonic compatibility (semitone/tritone = clash risk)
- energy: 0-1 scale, manage trajectory
- danceability, valence: mood matching
- instrumentalness: vocal collision risk

Use lyrics analysis:
- themes: narrative continuity
- moods: emotional flow
- narrative_style: storytelling coherence

Consider recent transition types to maintain variety."""
        
        user_prompt = f"""
User Controls:
- Mood: {user_controls.get('mood', 0.5)} (0=calm, 1=energetic)
- Genres: {user_controls.get('genres', [])}
- Prompt: {user_controls.get('prompt', 'None')}

Current Session History (last 5 tracks):
{json.dumps(session_history[:5], indent=2)}

Global Recent History (last 10 tracks, avoid repeats):
{json.dumps(global_history[:10], indent=2)}

Available Songs:
{json.dumps(available_songs[:20], indent=2)}

Preference: prioritize songs not appearing in either history; only reuse recent tracks if they are the sole musically coherent option.

Select the best next track. Respond with JSON:
{{
  "selected_uuid": "song-uuid-here",
  "rationale": "Why this track fits",
  "energy_match": 0.8,
  "genre_match": true,
  "recency_ok": true
}}
"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        return await self.chat_completion(
            messages=messages,
            temperature=0.7,
            thinking_budget=thinking_budget,
            json_mode=True
        )
    
    async def generate_transition_plan(
        self,
        song_a: Dict[str, Any],
        song_b: Dict[str, Any],
        thinking_budget: int = 1500
    ) -> Optional[Dict[str, Any]]:
        """
        Generate transition filtergraph between two songs.
        
        Args:
            song_a: Current song with features
            song_b: Next song with features
            thinking_budget: Reasoning token budget
        
        Returns:
            Dict with transition type and FFmpeg filtergraph
        """
        system_prompt = """You are an expert DJ transition planner with deep knowledge of transition techniques.

DECISION FRAMEWORK (choose transition in 20 seconds):
1. Analyze BPM relationship: same (±2 BPM) / close (±5-10 BPM) / far (>10 BPM) / half-double
2. Check key compatibility: compatible keys? heavy melodic overlap? clashing keys (semitone/tritone)?
3. Assess energy: next track higher / lower / same energy?
4. Check density: vocals or hooks that will collide?

TRANSITION FAMILIES & WHEN TO USE:

1. STRAIGHT BLEND (crossfade):
   - Use when: tempo ±5 BPM, compatible keys, similar energy
   - Best for: steady energy, long-format sets, warmups
   - FFmpeg: [0:a]atrim=...asetpts=PTS-STARTPTS[a];[1:a]atrim=...asetpts=PTS-STARTPTS[b];[a][b]acrossfade=d=3:c1=tri:c2=tri[out]
   - Pitfalls: double-bass muddiness, vocal clash

2. BASS SWAP:
   - Use when: similar tempo but different key signatures, maintaining groove
   - Best for: house/techno/EDM, kick-driven music
   - FFmpeg: Split frequencies with lowpass/highpass, swap bass ownership at downbeat
   - Why it works: only one dominant bassline avoids mud

3. FILTER BLEND (HPF/LPF):
   - Use when: smoothing harmonic clashes, breakdown transitions, adding tension
   - Best for: awkward key relationships, breakdown-to-breakdown
   - FFmpeg: Apply lowpass/highpass sweep on A, fade out, bring in B
   - Parameters: filter cutoff, sweep speed (phrase-length)

4. SLAM CUT:
   - Use when: tempo >10 BPM apart, clashing keys (semitone/tritone), energy jumps, vocal collisions
   - Best for: genre changes, crowd resets, dramatic pivots
   - FFmpeg: [0:a]afade=t=out:st=28:d=2[fade];[1:a]atrim=0:30[b];[fade][b]amix[out]
   - Key: timing must be tight, phrase-aligned

5. ECHO OUT:
   - Use when: emergency exits, key clashes, vocal transitions, vibe changes
   - Best for: leaving any situation cleanly, jumping into new vibe
   - FFmpeg: [0:a]atrim=start=0:duration=30,asetpts=PTS-STARTPTS[a];[a]aecho=0.8:0.9:0.250:0.5[echo];[echo]afade=t=out:st=28:d=2[fade];[1:a]atrim=start=0:duration=30,asetpts=PTS-STARTPTS[b];[fade][b]amix=duration=first[out]
   - Parameters: beat-synced delay (0.250s = 1/4 beat at 120 BPM), feedback 0.3-0.5
   - CRITICAL: aecho syntax is in_gain:out_gain:delay_seconds:decay (NOT milliseconds, NO pipes)

6. REVERB OUT (wash out):
   - Use when: energy downshifts, breakdown-to-breakdown, reset moments
   - Best for: dramatic dissolves, "reset the room"
   - FFmpeg: [0:a]areverb=...wet_gain=0.5[reverb];[reverb]afade=t=out:st=27:d=3[a];[1:a]atrim=0:30[b];[a][b]amix[out]
   - Pitfalls: too much reverb muddies, steals impact

7. DELAY THROW (dub echo):
   - Use when: tech-house/house, reggae/dub influence, groove transitions
   - Best for: rhythmic repeats on vocal/stab
   - FFmpeg: [0:a]atrim=start=0:duration=30,asetpts=PTS-STARTPTS[a];[a]asplit=2[dry][wet];[wet]adelay=250|250[delayed];[dry][delayed]amix=duration=first:weights=1.0 0.4[mixed];[mixed]afade=t=out:st=28.5:d=1.5[fade];[1:a]atrim=start=0:duration=30,asetpts=PTS-STARTPTS[b];[fade][b]amix=duration=first[out]
   - CRITICAL: adelay uses milliseconds with pipe for stereo (250|250), must use asplit first

8. WORDPLAY/LYRIC HANDOFF:
   - Use when: hip-hop, pop, open format where lyrics matter
   - Best for: clever lyric connections, vocal moments
   - Method: echo last word of A, drop B on matching word
   - FFmpeg: Echo last word, overlap with B's first word, quick transition

9. LOOP ROLL:
   - Use when: creating builds, filling gaps before drops, high-energy transitions
   - Best for: peak-time moments, tension building
   - Method: rolling stutter that tightens (1 beat → 1/8), release into drop

RULES:
- Tempo difference: ±2 BPM = blend, ±5-10 = filter blend, >10 = slam/echo-out
- Key clash: semitone/tritone = slam cut or bass swap
- Energy: up = quick transition (cut/roll), down = reverb/echo-out
- Vocals: overlapping vocals = avoid blend, use cut/swap/wordplay
- Always phrase-align: transitions cleanest on downbeat/phrase boundary

FFMPEG SYNTAX RULES (CRITICAL):
- atrim: Use "atrim=start=X:duration=Y" NOT "atrim=duration=Y"
- aecho: Use "aecho=in_gain:out_gain:delay_seconds:decay" (delay in SECONDS, single tap)
  Example: aecho=0.8:0.9:0.250:0.5 (NOT 250|500 format)
- adelay: Use milliseconds with pipe for stereo: "adelay=250|250" (requires asplit first)
- Always use asetpts=PTS-STARTPTS after atrim
- amix: Use "duration=first" or "duration=shortest"
- All filtergraphs must start with [0:a] or [1:a], end with [out]

Generate FFmpeg filtergraph using ONLY whitelisted filters: afade, acrossfade, volume, atrim, adelay, aformat, aecho, areverb, acompressor, sidechaincompress, anull, amix, amerge, asplit, asetrate, atempo, asetpts, bandpass, highpass, lowpass, equalizer, alimiter, aresample, aloop, concat.

Segment duration: 30 seconds. Inputs: [0:a] = song A (if exists), [1:a] = song B, [2:a] = TTS (if exists)."""
        
        user_prompt = f"""
Song A (current):
{json.dumps(song_a, indent=2)}

Song B (next):
{json.dumps(song_b, indent=2)}

Generate transition. Respond with JSON:
{{
  "transition_type": "straight_blend",
  "rationale": "Similar tempo and compatible keys, smooth blend works well",
  "ffmpeg": {{
    "filter_complex": "[0:a]atrim=start=0:duration=30,asetpts=PTS-STARTPTS[a];[1:a]atrim=start=0:duration=30,asetpts=PTS-STARTPTS[b];[a][b]acrossfade=d=3:c1=tri:c2=tri[out]",
    "map": "[out]"
  }},
  "duration_sec": 30
}}

IMPORTANT SYNTAX:
- Always use start=X:duration=Y in atrim (NOT just duration=Y)
- aecho uses seconds for delay (0.250 not 250)
- No pipes in aecho (use single tap: in:out:delay:decay)
- adelay uses milliseconds with pipes (250|250) but requires asplit first
"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        return await self.chat_completion(
            messages=messages,
            temperature=0.5,
            thinking_budget=thinking_budget,
            json_mode=True
        )
    
    async def generate_search_queries(
        self,
        user_preferences: List[str],
        raw_context: str,
        history: List[Dict[str, Any]] = None,
        count: int = 5
    ) -> Optional[Dict[str, Any]]:
        """
        Generate search queries based on user preferences using AI.
        
        Args:
            user_preferences: List of user music preferences from context file
            raw_context: Raw user context text
            history: Recent play history to avoid repetition
            count: Number of queries to generate
        
        Returns:
            Dict with search queries list
        """
        system_prompt = """You are generating search queries for a music API.

CRITICAL RULES - THE API WILL FAIL IF YOU DON'T FOLLOW THESE:
1. ONLY output real artist names or real song titles
2. NEVER output genre names, era descriptions, or mood descriptions
3. Each query must be something you'd type to search for a specific artist on Spotify

WRONG (API returns 0 results):
- "Synth-pop UK" ❌
- "80s British pop anthems" ❌  
- "Modern pop" ❌
- "upbeat dance hits" ❌
- "70s classics" ❌

CORRECT (API finds songs):
- "Queen" ✓
- "ABBA" ✓
- "Dua Lipa" ✓
- "Bohemian Rhapsody" ✓
- "Wham" ✓
- "Elton John" ✓

MAPPING USER PREFERENCES TO ARTISTS & SONGS:
- "modern pop" → Dua Lipa, Harry Styles, The Weeknd
- "latest hits" → Search for specific recent artists like "Dua Lipa" or "The Weeknd"
- "70s/80s UK" → Queen, ABBA, Elton John

Output JSON with "queries" array containing ONLY real artist names or song titles (max 5 query strings)."""
        
        recent_artists = []
        if history:
            recent_artists = [h.get('artist', '') for h in history[:10] if h.get('artist')]
        
        user_prompt = f"""
User Preferences:
{json.dumps(user_preferences, indent=2)}

Recently Played Artists (avoid these):
{json.dumps(recent_artists, indent=2)}

Based on these preferences, output {count} search queries (ARTIST NAMES or SONG TITLES) that will find relevant songs on Soundcharts.
Focus on artists who are likely to have "new and popular" content matching the mood and genres.

REMEMBER: Output ONLY specific artist names or song titles - NOT descriptions like "80s pop" or "synth-pop UK".
DO NOT include "Latest songs by" or "Top tracks by" in the query string itself.

Respond with JSON:
{{
  "queries": ["Dua Lipa", "Queen", "ABBA", "Harry Styles", "Blinding Lights"]
}}
"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        return await self.chat_completion(
            messages=messages,
            temperature=0.3,  # Low temperature for predictable artist names
            thinking_budget=500,
            json_mode=True
        )
    
    async def generate_dj_intro_speech(
        self,
        song_info: Dict[str, Any],
        user_context: str,
        thinking_budget: int = 3000
    ) -> Optional[Dict[str, Any]]:
        """
        Generate DJ intro speech for the start of a set.
        
        Args:
            song_info: Info about the first song (title, artist, uuid)
            user_context: User personalization info
            thinking_budget: Reasoning token budget
        
        Returns:
            Dict with speech text and metadata
        """
        system_prompt = f"""You are a witty, personable DJ starting a new set for a listener.

CONTEXT:
- User: {user_context}
- This is the OPENING of the set - the very first song
- Create excitement and set the mood

STYLE GUIDELINES:
- Brief: 2-4 sentences maximum
- Warm greeting: Acknowledge the listener personally if you know their name
- Set the vibe: Hint at what kind of musical journey you're about to take them on
- Natural: Conversational, like a friend starting a party
- Reference the first song or artist if you have that info

EXAMPLES OF GOOD INTROS:
- "Hey there! Ready to kick things off? I've got something special lined up..."
- "Alright, let's get this party started! First up, we're diving into..."
- "Welcome back! I've been waiting to play this one for you..."

AVOID:
- Being too formal or radio-DJ cliché
- Long explanations
- Generic phrases like "stay tuned" or "coming up next"
- Overusing catchphrases"""
        
        user_prompt = f"""
First Song Info:
{json.dumps(song_info, indent=2)}

Generate a DJ intro speech to kick off the set. Respond with JSON:
{{
  "text": "Your DJ intro speech here",
  "tone": "excited",
  "references": []
}}
"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        return await self.chat_completion(
            messages=messages,
            temperature=0.9,
            thinking_budget=thinking_budget,
            json_mode=True
        )
    
    async def generate_dj_speech(
        self,
        context: Dict[str, Any],
        user_context: str,
        thinking_budget: int = 3000
    ) -> Optional[Dict[str, Any]]:
        """
        Generate humorous DJ speech script.
        
        Args:
            context: Current DJ context (songs, transitions, mood)
            user_context: User personalization info
            thinking_budget: Reasoning token budget (high for creativity)
        
        Returns:
            Dict with speech text and metadata
        """
        system_prompt = f"""You are a witty, personable DJ creating short spoken intros/outros.

CONTEXT:
- User: {user_context}
- Transition type: Reference the transition technique being used (e.g., "smooth blend", "hard cut", "echo out") - make subtle jokes about it
- Song themes: Use lyrics analysis themes/moods for context
- Previous songs: Reference recent tracks for continuity

STYLE GUIDELINES:
- Brief: 1-3 sentences maximum
- Natural: Conversational, not scripted
- Humorous: Witty but not cheesy, occasional self-deprecating jokes
- Personalized: Reference user preferences from context
- Factual: Reference real chart positions, release dates, cultural impact when relevant
- Transition-aware: Subtle references to transition type ("smooth handoff", "hard reset", etc.)

TOOLS AVAILABLE:
- Use Firecrawl MCP to fetch real facts about artists/songs if needed
- Reference actual chart positions, release dates, cultural impact
- Use lyrics themes for narrative connections

AVOID:
- Overusing catchphrases
- Being too cheesy or radio-DJ cliché
- Long explanations
- Forcing humor when it doesn't fit"""
        
        user_prompt = f"""
Current Context:
{json.dumps(context, indent=2)}

Generate DJ speech. Respond with JSON:
{{
  "text": "Your DJ speech here",
  "tone": "humorous",
  "references": ["fact1", "fact2"]
}}
"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        return await self.chat_completion(
            messages=messages,
            temperature=0.9,
            thinking_budget=thinking_budget,
            json_mode=True
        )


# Global client instance
_openrouter_client: Optional[OpenRouterClient] = None


def get_openrouter_client() -> OpenRouterClient:
    """Get or create global OpenRouter client."""
    global _openrouter_client
    if _openrouter_client is None:
        _openrouter_client = OpenRouterClient()
    return _openrouter_client

