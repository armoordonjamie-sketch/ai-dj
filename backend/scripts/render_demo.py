import os
import wave
import math
import sys

# Fix import for script running from backend/scripts directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend.ffmpeg_runner import run_ffmpeg_render

# Generate two simple test WAV files with tones

def generate_tone(filename: str, duration_sec: int, freq_hz: float, sample_rate=44100):
    n_samples = int(sample_rate * duration_sec)
    amplitude = 32767
    with wave.open(filename, 'w') as wf:
        wf.setnchannels(1)  # mono
        wf.setsampwidth(2)  # bytes
        wf.setframerate(sample_rate)
        for i in range(n_samples):
            sample = int(amplitude * math.sin(2 * math.pi * freq_hz * i / sample_rate))
            wf.writeframesraw(sample.to_bytes(2, 'little', signed=True))


def main():
    tone_a = 'tone_a.wav'
    tone_b = 'tone_b.wav'
    output_file = 'rendered_output.wav'

    # Generate tones if not present
    if not os.path.exists(tone_a):
        generate_tone(tone_a, 35, 440.0)
    if not os.path.exists(tone_b):
        generate_tone(tone_b, 35, 660.0)

    # Crossfade filtergraph example - 30s segment
    filter_complex = (
        '[0:a]atrim=0:30,asetpts=PTS-STARTPTS[a0];'
        '[1:a]atrim=0:30,asetpts=PTS-STARTPTS[a1];'
        '[a0][a1]acrossfade=d=3:c1=tri:c2=tri[out]'
    )

    try:
        success = run_ffmpeg_render(
            input_files=[tone_a, tone_b],
            filter_complex=filter_complex,
            map_targets=['[out]'],
            output_path=output_file,
            segment_secs=30
        )
        if success:
            print(f'Rendered demo output to {output_file}')
        else:
            print('Failed to render demo output')
    except Exception as e:
        print(f'Error during render: {e}')


if __name__ == '__main__':
    main()
