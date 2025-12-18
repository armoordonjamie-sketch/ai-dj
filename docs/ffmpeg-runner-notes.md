# FFmpeg Runner Notes

## Filtergraph Whitelist Rules

- Only allow audio filters from a strict whitelist to prevent arbitrary or unsafe operations.
- Maximum allowed filter_complex string length: 1000 characters.
- Filters allowed include: `afade`, `acrossfade`, `volume`, `atrim`, `adelay`, `aformat`, `aecho`, `areverb`, `acompressor`, `anull`, `amix`, `amerge`, `asetrate`, `atempo`, `asetpts`, `bandpass`, `highpass`, `lowpass`.
- Filtergraph must be parsed at a basic level to identify allowed filters. Complex parsing not implemented yet; presence of allowed filters checked.

## Security Considerations

- No shell=True usage in subprocess, only argument list passed.
- Inputs checked for existence.
- Basic length and content validation of filtergraph.

## Example Filtergraph

```bash
-filter_complex "[0:a]atrim=0:30,asetpts=PTS-STARTPTS[a0];[1:a]atrim=0:30,asetpts=PTS-STARTPTS[a1];[a0][a1]acrossfade=d=3:c1=tri:c2=tri[out]"
-map [out]
```

- This generates a 30-second crossfade between two input streams.

## Current Status

- Implemented safe FFmpeg execution layer in `backend/ffmpeg_runner.py`.
- Executes with subprocess argument list, no shell execution.
- Validates input files and filtergraph content.
- Whitelisted filters enforced.
- Demo script added as `backend/scripts/render_demo.py` which generates test tones and runs a crossfade render.
- Demo successfully tested producing output audio file.
- Segment storage is stubbed with a placeholder function pending database integration.

## Future Work

- Integrate segment DB storage when database layer is ready.
- Enhance filtergraph validation logic.
- Add support for video filtergraph if needed.

