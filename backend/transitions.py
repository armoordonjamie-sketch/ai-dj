"""FFmpeg-python transition library for AI DJ.

This module provides DJ transition effects using the ffmpeg-python library.
All transitions expect standardized streams (44.1kHz, stereo) and provide
surgical filter logic that is only active during the transition window.

Adapted from v2.0 transition engine.
"""
import ffmpeg


def apply_crossfade(a1, a2, duration: float):
    """
    Standard linear crossfade using tri curve for constant power.
    
    Args:
        a1: ffmpeg-python audio stream for outgoing track
        a2: ffmpeg-python audio stream for incoming track
        duration: Crossfade duration in seconds
        
    Returns:
        ffmpeg-python audio stream with crossfade applied
    """
    return ffmpeg.filter([a1, a2], 'acrossfade', d=duration, c1='tri', c2='tri')


def apply_bass_swap(a1, a2, duration: float, peak_time: float):
    """
    Surgical Bass Swap transition.
    
    Performs a frequency-split swap where:
    - Uses clean audio before/after transition
    - Applies steep filters only during the transition overlap
    - Ensures all bands stay perfectly in sync
    - Crossfades high frequencies while instantaneously swapping 
      low frequencies (below 250Hz) at the peak_time
    
    Args:
        a1: ffmpeg-python audio stream for outgoing track
        a2: ffmpeg-python audio stream for incoming track  
        duration: Total transition duration in seconds
        peak_time: Absolute time when bass swap occurs
        
    Returns:
        ffmpeg-python audio stream with bass swap applied
    """
    fade_start = peak_time - (duration / 2)
    fade_end = peak_time + (duration / 2)
    
    # Split track A into 3 streams: low, high, clean
    a1_split = a1.filter_multi_output('asplit', outputs=3)
    # Linkwitz-Riley 24dB/oct approach (steeper, cleaner)
    a1_low = a1_split[0].filter('lowpass', f=250).filter('lowpass', f=250)
    a1_high = a1_split[1].filter('highpass', f=250).filter('highpass', f=250)
    a1_clean = a1_split[2]
    
    # Split track B into 3 streams: low, high, clean
    a2_split = a2.filter_multi_output('asplit', outputs=3)
    a2_low = a2_split[0].filter('lowpass', f=250).filter('lowpass', f=250)
    a2_high = a2_split[1].filter('highpass', f=250).filter('highpass', f=250)
    a2_clean = a2_split[2]
    
    # 1. Outgoing Track (A1) logic:
    # Highs: fade out during the window
    a1_high_v = a1_high.filter('volume', f'if(between(t,{fade_start},{fade_end}), ({fade_end}-t)/{duration}, 0)', eval='frame')
    # Lows: stay at 1 until the swap point
    a1_low_v = a1_low.filter('volume', f'if(between(t,{fade_start},{peak_time}), 1, 0)', eval='frame')
    # Clean: only before the window
    a1_clean_v = a1_clean.filter('volume', f'if(lt(t,{fade_start}), 1, 0)', eval='frame')

    # 2. Incoming Track (A2) logic:
    # Highs: fade in during the window
    a2_high_v = a2_high.filter('volume', f'if(between(t,{fade_start},{fade_end}), (t-{fade_start})/{duration}, 0)', eval='frame')
    # Lows: start at the swap point
    a2_low_v = a2_low.filter('volume', f'if(between(t,{peak_time},{fade_end}), 1, 0)', eval='frame')
    # Clean: only after the window
    a2_clean_v = a2_clean.filter('volume', f'if(gt(t,{fade_end}), 1, 0)', eval='frame')

    # Mix all 6 streams together
    return ffmpeg.filter(
        [a1_clean_v, a1_high_v, a1_low_v, a2_clean_v, a2_high_v, a2_low_v], 
        'amix', 
        inputs=6, 
        duration='longest', 
        normalize=0
    )


def apply_filter_sweep(a1, a2, duration: float):
    """
    LPF sweep transition.
    
    Incoming track B starts muffled and opens up.
    Outgoing track A starts full and closes down.
    
    Note: True animated sweeps are tricky with acrossfade because 't' restarts.
    This uses a standard crossfade as a baseline implementation.
    
    Args:
        a1: ffmpeg-python audio stream for outgoing track
        a2: ffmpeg-python audio stream for incoming track
        duration: Crossfade duration in seconds
        
    Returns:
        ffmpeg-python audio stream with filter sweep applied
    """
    # For now, use standard crossfade - a true sweep requires manual mixing
    return ffmpeg.filter([a1, a2], 'acrossfade', d=duration, c1='tri', c2='tri')


def apply_echo_out(a1, a2, duration: float):
    """
    Echo out transition with feedback delay tail.
    
    Applies a feedback delay to the outgoing track while crossfading 
    into the incoming track.
    
    Args:
        a1: ffmpeg-python audio stream for outgoing track
        a2: ffmpeg-python audio stream for incoming track
        duration: Crossfade duration in seconds
        
    Returns:
        ffmpeg-python audio stream with echo out applied
    """
    # Boost decay for a more 'pro' trail
    # aecho params: in_gain, out_gain, delays_ms, decays
    a1_echo = a1.filter('aecho', 0.8, 0.88, 500, 0.5)
    return ffmpeg.filter([a1_echo, a2], 'acrossfade', d=duration, c1='tri', c2='tri')


def apply_vinyl_stop(a1, a2, stop_duration: float = 2.0):
    """
    Turntable brake effect (vinyl stop).
    
    Creates a dramatic slowdown effect on the outgoing track,
    simulating a turntable being stopped.
    
    Note: A true pitch-bend slowdown using asetrate is tricky to time.
    This implementation uses volume fade + heavy echo as an approximation.
    
    Args:
        a1: ffmpeg-python audio stream for outgoing track
        a2: ffmpeg-python audio stream for incoming track
        stop_duration: Duration of the brake effect in seconds
        
    Returns:
        ffmpeg-python audio stream with vinyl stop applied
    """
    # Apply fade out and heavy echo for "wash" effect
    a1_brake = a1.filter('afade', t='out', d=stop_duration)
    a1_wash = a1_brake.filter('aecho', 0.8, 0.9, 100, 0.6)
    
    # Short crossfade after the brake
    return ffmpeg.filter([a1_wash, a2], 'acrossfade', d=1.0, c1='tri', c2='tri')


# Transition type registry for easy lookup
TRANSITION_FUNCTIONS = {
    'blend': apply_crossfade,
    'crossfade': apply_crossfade,
    'bass_swap': apply_bass_swap,
    'filter_sweep': apply_filter_sweep,
    'echo_out': apply_echo_out,
    'vinyl_stop': apply_vinyl_stop,
}


def get_transition_function(transition_type: str):
    """
    Get the transition function for a given type.
    
    Args:
        transition_type: One of 'blend', 'bass_swap', 'filter_sweep', 
                        'echo_out', 'vinyl_stop'
                        
    Returns:
        Transition function or apply_crossfade as fallback
    """
    return TRANSITION_FUNCTIONS.get(transition_type, apply_crossfade)

