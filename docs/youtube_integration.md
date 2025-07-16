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
youtube_channels:
  - name: "Channel Name"
    channel_id: "UCxxxxxx"  # YouTube channel ID
    url: "https://www.youtube.com/@channelname"  # Alternative to channel_id
    max_videos: 5  # Maximum videos to fetch
    min_duration: 600  # Minimum duration in seconds

youtube_playlists:
  - name: "Playlist Name"
    playlist_id: "PLxxxxxx"  # YouTube playlist ID
    max_videos: 10
    min_duration: 300

settings:
  download_audio: false  # Only get transcripts
  prefer_auto_captions: true  # Use auto-generated captions
  languages: ["en"]  # Preferred subtitle languages
  max_age_days: 30  # Only process recent videos
```

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
# Run only YouTube scraper
python scripts/run_scrapers.py --scrapers youtube

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
# Test YouTube URL detection
python scripts/test_youtube_simple.py

# Test full YouTube functionality
python scripts/test_youtube.py

# Check YouTube content in database
python scripts/check_content.py --type podcast --source youtube
```