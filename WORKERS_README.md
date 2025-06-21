# Sequential Task Processor

This system has been refactored from thread-based workers to a sequential processor for improved robustness and simplicity.

## Key Changes

1. **SequentialTaskProcessor** - The only task processor
   - Processes tasks one at a time sequentially
   - No threading complexity or race conditions
   - Simple, reliable, easy to debug

2. **Sync-First Architecture**
   - All pipeline operations are synchronous
   - Async libraries (crawl4ai, scrapers) wrapped in sync interfaces
   - No event loop conflicts or threading issues

3. **Clean Separation of Concerns**
   - `SyncWebCrawler` wraps crawl4ai's async operations
   - `SyncScraperWrapper` handles async scrapers
   - `SyncAsyncRunner` for any remaining async needs

## Running Workers

### Using Shell Scripts

```bash
# Run 4 workers (default)
./scripts/workers.sh

# Run 8 workers
./scripts/workers.sh 8

# Run scrapers and process content
./scripts/scrape.sh

# Process only pending tasks
./scripts/process.sh

# Show queue statistics
./scripts/stats.sh

# Run tests
./scripts/test.sh
```

### Direct Commands

```bash
# Run workers
python run_workers.py [num_workers]

# Run with detailed options
python scripts/run_workers.py --workers 4 --debug --stats-interval 30

# Run scrapers and process
python scripts/run_scrapers_unified.py --max-workers 4

# Process pending tasks only
python scripts/run_pending_tasks.py --max-workers 4
```

## Architecture

```
SequentialTaskProcessor
├── Single Execution Thread
│   ├── Processes tasks one at a time
│   ├── No concurrency issues
│   └── Simple error handling
├── Task Queue (database-backed)
│   ├── Pulls tasks from database
│   └── Updates task status after processing
└── Database Queue Service
    ├── Persistent task storage
    ├── Retry logic
    └── Task status tracking
```

## Task Types

- `SCRAPE` - Run web scrapers
- `PROCESS_CONTENT` - Process articles/podcasts
- `DOWNLOAD_AUDIO` - Download podcast audio files
- `TRANSCRIBE` - Transcribe audio to text
- `SUMMARIZE` - Generate content summaries

## Benefits

1. **No Event Loop Conflicts** - Thread-based approach avoids async complications
2. **Simpler Error Handling** - Synchronous code is easier to debug
3. **Better Compatibility** - Works with libraries that don't support async
4. **Graceful Shutdown** - Proper signal handling and worker cleanup

## Monitoring

The system provides real-time statistics:

```bash
# View queue stats
./scripts/stats.sh

# Monitor workers with periodic stats
python scripts/run_workers.py --stats-interval 10
```

## Troubleshooting

1. **Workers not processing tasks**
   - Check database connection
   - Verify tasks exist in queue: `./scripts/stats.sh`
   - Check logs in `logs/` directory

2. **SSL/Certificate errors**
   - The system handles SSL errors gracefully
   - Problem domains are logged but don't crash workers

3. **Memory usage**
   - Each worker runs in a thread (lighter than processes)
   - Adjust worker count based on available memory

## Testing

```bash
# Test the thread processor
python test_thread_processor.py

# Test HTML strategy event loop fix
python test_html_strategy_fix.py
```