# Podcast Processing Flow

## Overview

The podcast processing system is integrated into the unified content framework. Podcasts are treated as a content type alongside articles, with a specialized processing pipeline.

## Architecture

### Components

1. **Scraper** (`app/scraping/podcast_unified.py`)
   - Reads RSS feeds configured in `config/podcasts.yml`
   - Creates `Content` entries with `content_type='podcast'`
   - Stores podcast metadata (audio_url, duration, episode number, etc.)

2. **Workers** (`app/pipeline/podcast_workers.py`)
   - `PodcastDownloadWorker`: Downloads audio files
   - `PodcastTranscribeWorker`: Transcribes audio to text using Whisper

3. **Task Processor** (`app/pipeline/task_processor.py`)
   - Processes tasks from the queue
   - Routes tasks to appropriate workers
   - Handles retries and error recovery

4. **Queue Service** (`app/services/queue.py`)
   - Simple database-backed task queue
   - Supports different task types: DOWNLOAD_AUDIO, TRANSCRIBE, SUMMARIZE

## Processing Pipeline

```
1. RSS Scraping
   └─> Create Content entry (status='new')
       └─> Queue PROCESS_CONTENT task

2. Content Processing
   └─> Detect content_type='podcast'
       └─> Queue DOWNLOAD_AUDIO task

3. Audio Download
   └─> Download MP3/M4A file to data/podcasts/
       └─> Update content_metadata with file_path
           └─> Queue TRANSCRIBE task

4. Transcription
   └─> Load Whisper model
       └─> Transcribe audio to text
           └─> Save transcript to .txt file
               └─> Update content_metadata with transcript
                   └─> Queue SUMMARIZE task

5. Summarization
   └─> Extract transcript from content_metadata
       └─> Use LLM service to generate summary
           └─> Update content_metadata with summary
               └─> Mark content as 'completed'
```

## Database Schema

Podcasts use the unified `Content` model with podcast-specific data in `content_metadata`:

```python
{
    # From scraper
    'audio_url': str,           # URL to audio file
    'episode_number': int,      # Episode number if available
    'duration_seconds': int,    # Duration in seconds
    'feed_name': str,          # Podcast feed name
    'publication_date': str,    # ISO format date
    
    # From download worker
    'file_path': str,          # Local path to downloaded audio
    'download_date': str,      # ISO format date
    'file_size': int,          # File size in bytes
    
    # From transcribe worker
    'transcript': str,         # Full transcript text
    'transcript_path': str,    # Path to transcript file
    'transcription_date': str, # ISO format date
    'detected_language': str,  # Detected language code
    'language_probability': float,
    
    # From summarize worker
    'summary': str,            # LLM-generated summary
    'summarization_date': str  # ISO format date
}
```

## Configuration

### Podcast Feeds (`config/podcasts.yml`)

```yaml
feeds:
  - name: "Podcast Name"
    url: "https://example.com/rss"
    limit: 10  # Max episodes to fetch
```

### Worker Configuration

- Max workers: Configured in settings
- Retry policy: 3 attempts with exponential backoff
- Timeout: 300 seconds for downloads, configurable for other tasks

## Running the System

### Start Task Processor

```bash
# Run continuously
python -m app.pipeline.task_processor

# Run with worker pool
python scripts/run_task_processor.py --workers 4
```

### Manual Scraping

```bash
# Run all scrapers
python scripts/run_scrapers_unified.py

# Run only podcast scraper
python scripts/run_scrapers_unified.py --scraper podcast
```

## Monitoring

### Check Queue Status

```python
from app.services.queue import get_queue_service

queue = get_queue_service()
stats = queue.get_queue_stats()
print(stats)
```

### Database Queries

```sql
-- Pending podcasts
SELECT * FROM contents 
WHERE content_type = 'podcast' 
  AND status = 'new';

-- Failed podcasts
SELECT * FROM contents 
WHERE content_type = 'podcast' 
  AND status = 'failed';

-- Processing tasks
SELECT * FROM processing_tasks 
WHERE status = 'pending' 
ORDER BY created_at;
```

## Error Handling

1. **Download Failures**
   - Automatic retry with exponential backoff
   - Failed downloads marked in content.error_message
   - Partial downloads cleaned up automatically

2. **Transcription Failures**
   - Model loaded on-demand to save memory
   - Fallback to CPU if GPU unavailable
   - Language detection included in metadata

3. **Queue Failures**
   - Tasks remain in queue until explicitly completed
   - Stale checkouts released after timeout
   - Failed tasks can be manually retried

## Migration from Old System

The old podcast system (`app/podcast/`) remains for reference but is no longer used. To migrate existing data:

1. Map old `Podcast` table to new `Content` table
2. Convert status values to unified system
3. Extract metadata into content_metadata JSON field

See `scripts/migrate_podcast_data.py` for migration script (if needed).