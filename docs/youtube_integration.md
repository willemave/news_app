# YouTube Integration Documentation

## Overview

We've successfully integrated YouTube video processing into the news app, treating YouTube videos as podcasts. This allows the system to:

1. Scrape YouTube channels and playlists for new videos
2. Extract video metadata and transcripts
3. Process videos through the existing podcast pipeline
4. Summarize video content using AI

## Architecture

### 1. YouTube Scraper (`app/scraping/youtube_unified.py`)
- Reads channel and playlist configurations from `config/youtube.yml`
- Uses yt-dlp to fetch video metadata
- Creates content entries with `content_type=PODCAST`
- Supports filtering by:
  - Maximum age (default: 30 days)
  - Minimum duration
  - Maximum videos per channel

### 2. YouTube Processing Strategy (`app/processing_strategies/youtube_strategy.py`)
- Handles YouTube URLs when processing individual links
- Extracts video metadata using yt-dlp
- Downloads and parses subtitles/captions
- Supports multiple subtitle formats (VTT, SRV3, JSON3)
- Falls back to video description if no transcript available

### 3. Pipeline Integration
- **PodcastDownloadWorker**: Detects YouTube URLs and skips download, passing directly to transcription
- **PodcastTranscribeWorker**: Uses existing YouTube transcripts instead of OpenAI transcription
- **Summarization**: Works normally with transcript/description content

## Configuration

### config/youtube.yml

```yaml
channels:
  - name: "Lex Fridman Podcast"
    channel_id: "UCgxzjK6GuOHVKR_08TT4hJQ"
    url: "https://www.youtube.com/@lexfridman"
    limit: 5
    max_age_days: 30
    language: "en"

  - name: "All-In Podcast"
    url: "https://www.youtube.com/@allinpodcast"
    limit: 3
    max_age_days: 7
```

**Field reference**

| Field | Description |
| --- | --- |
| `name` | Friendly label displayed in logs and admin views |
| `url` | Channel/handle/playlist URL (optional if `channel_id` or `playlist_id` present) |
| `channel_id` | Raw channel identifier (e.g., `UC...`) |
| `playlist_id` | Optional playlist identifier to override the channel feed |
| `limit` | Maximum videos ingested per run (default 10, max 50) |
| `max_age_days` | Skip videos older than the threshold (`0` disables filtering) |
| `language` | Preferred transcript language hint propagated to metadata |

## Metadata Fields

YouTube videos are stored as podcasts with additional metadata:

- `video_url`: Original YouTube URL
- `video_id`: YouTube video ID
- `channel_name`: YouTube channel name
- `thumbnail_url`: Video thumbnail URL
- `view_count`: Number of views
- `like_count`: Number of likes
- `has_transcript`: Whether transcript is available
- `youtube_video`: Boolean flag to identify YouTube content

## Usage

### Running the YouTube Scraper

```bash
# Run only the YouTube scraper and persist to the DB
python scripts/run_scrapers.py --scrapers youtube

# Dry-run a single channel without writing to the DB
python scripts/test_youtube_scraper.py --name "Example" --url "https://www.youtube.com/@Example" --limit 2

# Run all scrapers including YouTube
python scripts/run_scrapers.py
```

### Processing Individual YouTube URLs

YouTube URLs are automatically detected and processed when:
1. Added manually through the API
2. Found as links in other content
3. Submitted through the UI

## Future Enhancements

1. **UI Improvements**: 
   - Display video thumbnails
   - Show view/like counts
   - Embed YouTube player

2. **Advanced Features**:
   - Support for live streams
   - Channel subscriptions with notifications
   - Video comments analysis
   - Playlist synchronization

3. **Performance**:
   - Parallel video processing
   - Incremental channel updates
   - Caching of video metadata

## Troubleshooting

### Common Issues

1. **No transcript available**: Some videos don't have captions. The system will use the video description instead.

2. **Rate limiting**: YouTube may rate limit requests. Consider adding delays between requests.

3. **Private/deleted videos**: These will be skipped automatically.

### Debug Commands

```bash
# Dry-run the scraper for a single channel and print results
python scripts/test_youtube_scraper.py --name "Example" --url "https://www.youtube.com/@Example" --limit 1

# Run only the YouTube scraper via the runner
python scripts/run_scrapers.py --scrapers youtube --show-stats

# Inspect stored YouTube content
python scripts/check_content.py --type podcast --platform youtube
```