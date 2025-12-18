# Soundcharts SDK Setup Guide

The AI DJ now uses the **official Soundcharts Python SDK** instead of direct HTTP calls.

## Installation

```bash
pip install soundcharts
```

Or install all dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

The SDK requires both `app_id` and `api_key` in your `.env` file:

```bash
SOUNDCHARTS_APP_ID=your-app-id-here
SOUNDCHARTS_API_KEY=your-api-key-here
```

## How It Works

Our `SoundchartsClient` wrapper now uses the official SDK:

```python
from soundcharts.client import SoundchartsClient

# Initialize (done automatically in our wrapper)
sc = SoundchartsClient(
    app_id="your_app_id",
    api_key="your_api_key"
)

# Search for songs
results = sc.search.search_song_by_name(name="Shake It Off", limit=10)

# Search for artists
artists = sc.search.search_artist_by_name(name="Taylor Swift", limit=10)

# Get song metadata
metadata = sc.song.get_song_metadata(uuid="song-uuid-here")

# Get lyrics analysis
lyrics = sc.song.get_lyrics_analysis(uuid="song-uuid-here")

# Get artist songs
songs = sc.artist.get_songs(uuid="artist-uuid-here")
```

## Benefits of Using Official SDK

1. **Maintained by Soundcharts**: Always up-to-date with API changes
2. **Built-in Error Handling**: Automatic retries and better error messages
3. **Parallel Processing**: SDK supports parallel requests for better performance
4. **Logging**: Configurable logging levels
5. **Type Safety**: Better IDE autocomplete and type hints

## Testing

Test your Soundcharts connection:

```bash
python backend/scripts/test_soundcharts.py
```

Expected output:
```
✅ Success! Found 3 songs:
  1. Shake It Off by Taylor Swift
     UUID: 11e81bcc-9c1c-ce38-b96b-a0369fe50396
  ...
```

## Troubleshooting

### SDK Not Installed
```
WARNING:root:Soundcharts SDK not installed. Run: pip install soundcharts
```
**Fix**: `pip install soundcharts`

### Invalid Credentials
```
ERROR:root:Soundcharts search error: ...
```
**Fix**: Verify your `SOUNDCHARTS_APP_ID` and `SOUNDCHARTS_API_KEY` in `.env`

### No Results
If search returns empty results but no error:
- Check your API subscription is active
- Verify you have access to the search endpoint
- Contact Soundcharts support

## SDK Documentation

- GitHub: https://github.com/soundcharts/python-sdk
- Soundcharts API Docs: https://api.soundcharts.com/docs
- Support: Contact Soundcharts support team

## Advanced Usage

### Parallel Requests

The SDK supports parallel processing for bulk operations:

```python
sc = SoundchartsClient(
    app_id="your_app_id",
    api_key="your_api_key",
    parallel_requests=10  # Run 10 requests in parallel
)
```

### Custom Logging

```python
import logging

sc = SoundchartsClient(
    app_id="your_app_id",
    api_key="your_api_key",
    console_log_level=logging.INFO,
    file_log_level=logging.WARNING,
    exception_log_level=logging.ERROR
)
```

## Migration Notes

We've migrated from direct HTTP calls to the official SDK:

**Before** (custom HTTP client):
```python
async with httpx.AsyncClient() as client:
    response = await client.get(
        f"{base_url}/song/search",
        headers={"x-app-id": app_id, "x-api-key": api_key},
        params={"query": query}
    )
```

**After** (official SDK):
```python
results = self.client.search.search_song(query=query, limit=10)
```

Much simpler and more reliable!

