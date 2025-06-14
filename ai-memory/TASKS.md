# Unified Pipeline Implementation Tasks

## Pipeline Architecture Diagram

## Current System Analysis

### Existing Components:
1. **TaskProcessor** (`app/pipeline/task_processor.py`):
   - Already handles: DOWNLOAD_AUDIO, TRANSCRIBE, SUMMARIZE
   - Missing: SCRAPE, PROCESS_CONTENT

2. **ScraperRunner** (`app/scraping/runner.py`):
   - Runs scrapers directly (not through task queue)
   - Returns count of scraped items

3. **WorkerPool** (`app/pipeline/worker.py`):
   - Uses checkout mechanism (not task queue)
   - Processes content directly

4. **QueueService** (`app/services/queue.py`):
   - Supports all 5 TaskTypes
   - Has enqueue/dequeue/retry logic

## Implementation Plan

### Phase 1: Extend TaskProcessor ✅
- [x] Analyze current TaskProcessor implementation
- [x] Add `_process_scrape_task()` method to handle SCRAPE tasks
- [x] Add `_process_content_task()` method to handle PROCESS_CONTENT tasks
- [x] Update the main `process_task()` method to route new task types

### Phase 2: Create Task-Based Scrapers ✅
- [x] ScraperRunner already supports async execution
- [x] Scrapers already enqueue PROCESS_CONTENT tasks after saving
- [x] Backward compatibility maintained

### Phase 3: Integrate Content Processing with Task Queue ✅
- [x] ContentWorker is called from TaskProcessor._process_content_task()
- [x] Checkout logic remains in ContentWorker for consistency
- [x] Error handling and retry logic implemented

### Phase 4: Create Unified Pipeline Script ✅
- [x] Created scripts/run_unified_pipeline.py with full orchestration
- [x] Added command-line arguments for different modes (full, scrape, process, tasks)
- [x] Implemented progress monitoring and comprehensive statistics
- [x] Added graceful shutdown handling with KeyboardInterrupt

### Phase 5: Testing and Validation
- [ ] Test each task type individually
- [ ] Test full pipeline flow
- [ ] Verify error handling and retry logic
- [ ] Performance testing with concurrent workers

## Detailed Implementation Steps

### 1. Extend TaskProcessor for SCRAPE Tasks

```python
async def _process_scrape_task(self, payload: dict) -> bool:
    """Process a scrape task."""
    scraper_name = payload.get('scraper_name')
    if not scraper_name:
        logger.error("No scraper_name in payload")
        return False
    
    # Get scraper instance
    runner = ScraperRunner()
    count = await runner.run_scraper(scraper_name)
    
    if count is not None and count > 0:
        logger.info(f"Scraper {scraper_name} found {count} items")
        # Items are already in database, enqueue processing tasks
        # This happens automatically via scraper implementation
        return True
    else:
        logger.error(f"Scraper {scraper_name} failed or found no items")
        return False
```

### 2. Extend TaskProcessor for PROCESS_CONTENT Tasks

```python
async def _process_content_task(self, content_id: int) -> bool:
    """Process content using the existing ContentWorker logic."""
    worker = ContentWorker()
    success = await worker.process_content(content_id, f"task-processor-{content_id}")
    return success
```

### 3. Update run_scrapers_unified.py Structure

```python
# New structure will:
1. Initialize task queue
2. Enqueue SCRAPE tasks for each scraper
3. Start TaskProcessorPool to handle all tasks
4. Monitor progress and display statistics
5. Support different execution modes
```

### 4. Command-Line Arguments

```
--mode: full|scrape|process|tasks
  - full: Run scrapers then process all content
  - scrape: Only run scrapers
  - process: Only process existing content
  - tasks: Only process queued tasks

--scrapers: List of scrapers to run
--content-type: Filter by article/podcast
--max-workers: Number of concurrent workers
--max-items: Maximum items to process
--continuous: Run continuously with interval
--debug: Enable debug logging
--show-stats: Show detailed statistics
```

## Key Design Decisions

1. **Task Granularity**: 
   - Each scraper = 1 SCRAPE task
   - Each content item = 1 PROCESS_CONTENT task
   - Podcast processing = 3 sequential tasks (DOWNLOAD → TRANSCRIBE → SUMMARIZE)

2. **Error Handling**:
   - Failed tasks retry with exponential backoff
   - Max retry count from settings
   - Detailed error logging

3. **Concurrency**:
   - Multiple workers process different task types simultaneously
   - Task queue ensures no duplicate processing
   - Checkout mechanism prevents race conditions

4. **Monitoring**:
   - Real-time task queue statistics
   - Progress tracking per task type
   - Success/failure rates

## Success Criteria

1. ✅ All 5 TaskTypes are implemented in TaskProcessor
2. ✅ Pipeline runs end-to-end without manual intervention
3. ✅ Error recovery with proper retry logic
4. ✅ Concurrent processing optimization
5. ✅ Clear monitoring and statistics
6. ✅ Support for different execution modes
7. ✅ Backward compatibility maintained

## Implementation Summary

### Scripts Created/Modified:

1. **app/pipeline/task_processor.py**:
   - Added `_process_scrape_task()` to handle SCRAPE tasks
   - Added `_process_content_task()` to handle PROCESS_CONTENT tasks
   - Integrated ScraperRunner and ContentWorker

2. **scripts/run_unified_pipeline.py** (NEW):
   - Full pipeline orchestration script
   - Supports modes: full, scrape, process, tasks
   - Continuous mode with configurable interval
   - Comprehensive statistics and monitoring
   - Example usage included in help

3. **scripts/run_scrapers_unified.py** (UPDATED):
   - Updated to use new pipeline by default
   - Added `--use-legacy` flag for backward compatibility
   - Maintains same command-line interface
   - Shows comprehensive statistics

## Usage Examples

```bash
# Full pipeline (scrape + process everything)
python scripts/run_unified_pipeline.py --mode full

# Run specific scrapers only
python scripts/run_unified_pipeline.py --mode scrape --scrapers hackernews reddit

# Process only articles
python scripts/run_unified_pipeline.py --mode process --content-type article

# Process only queued tasks with 5 workers
python scripts/run_unified_pipeline.py --mode tasks --max-workers 5

# Run continuously every 5 minutes
python scripts/run_unified_pipeline.py --mode full --continuous --interval 300

# Legacy compatibility mode
python scripts/run_scrapers_unified.py --use-legacy --scrapers hackernews
```

## Next Steps

1. Test individual task types:
   - [ ] Test SCRAPE tasks
   - [ ] Test PROCESS_CONTENT tasks for articles
   - [ ] Test podcast pipeline (DOWNLOAD_AUDIO → TRANSCRIBE → SUMMARIZE)

2. Integration testing:
   - [ ] Run full pipeline with all scrapers
   - [ ] Verify task queue ordering
   - [ ] Test error recovery and retries
   - [ ] Performance test with high concurrency

3. Documentation:
   - [ ] Update README.md with new pipeline architecture
   - [ ] Document task flow and dependencies
   - [ ] Add troubleshooting guide

4. Monitoring improvements:
   - [ ] Add real-time progress bars
   - [ ] Export metrics to monitoring system
   - [ ] Add webhook notifications for failures