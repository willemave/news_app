# Refactor Link Processing System with a Queue

This document outlines the tasks required to refactor the link processing system to use a dedicated "links_to_scrape" queue, a new processor, and to change how raw content is handled.

## New Dependencies
- (Potentially none if Huey is sufficient, otherwise list any new queueing libraries if chosen)

## Phase 1: Queue Setup and Scraper Modification

**Phase Goal:** Implement the "links_to_scrape" queue and modify existing scrapers to populate it.

**Tasks:**
- [x] **Define "links_to_scrape" Queue:**
    - [x] Decide on queue technology. Given `SqliteHuey` is already in `app/queue.py`, investigate extending it or creating a new Huey instance for `links_to_scrape`.
    - [x] Define the task signature for items placed on this queue (e.g., `process_link_task(url: str, source: str)`).
    - [x] Implement the Huey task definition in `app/queue.py` or a new dedicated queue file if preferred.
- [x] **Modify `app/scraping/hackernews_scraper.py`:**
    - [x] Remove direct article creation/summarization logic.
    - [x] Instead of direct processing, add discovered external article URLs to the "links_to_scrape" queue.
    - [x] Ensure relevant metadata (like source) is passed to the queue task if needed.
- [x] **Modify `app/scraping/reddit.py`:**
    - [x] Remove direct article creation/summarization logic.
    - [x] Instead of direct processing, add discovered article URLs to the "links_to_scrape" queue.
    - [x] Ensure relevant metadata (like source, original post details) is passed to the queue task.
- [x] **Implement Basic Retry for Queue Tasks:**
    - [x] Configure Huey task retries for the new `process_link_task`. If a task fails due to transient issues (not LLM 429 specifically yet), Huey should retry it.
- [x] **Update `ai-memory/TASKS.md`** with key learnings, decisions, pivots, or any unresolved issues from this Phase before proceeding to the next.

**Reference Files:**
- `app/queue.py`
- `app/scraping/hackernews_scraper.py`
- `app/scraping/reddit.py`
- `app/config.py` (for Huey settings)

**Key Learnings/Decisions from this Phase:**
- **Queue Technology Decision:** Extended the existing `SqliteHuey` instance in `app/queue.py` rather than creating a new queue system. This maintains consistency with the existing infrastructure.
- **Task Signature:** Implemented `process_link_task(url: str, source: str = "unknown")` with retry configuration (retries=3, retry_delay=60).
- **Scraper Refactoring:** Successfully simplified both `hackernews_scraper.py` and `reddit.py` by removing all content downloading, processing, and database operations. They now only discover links and queue them.
- **Source Tracking:** Added source metadata to track where links originated (e.g., "hackernews", "reddit-front", "reddit-programming").
- **Backward Compatibility:** Maintained existing function signatures but changed their behavior to use the queue system.
- **Removed Dependencies:** Eliminated imports for database operations, LLM processing, and content scraping from the scrapers, making them much lighter and focused.

## Phase 2: Create `app/processor.py` - The Link Processor

**Phase Goal:** Develop a new processor that consumes links from the queue, downloads content, processes it with an LLM, and creates articles.

**Tasks:**
- [x] **Create `app/processor.py`:**
    - [x] This file will contain the logic for the consumer of the "links_to_scrape" queue.
- [x] **Implement Queue Consumer Task:**
    - [x] Define a Huey task (e.g., `consume_link_and_process(url: str, source: str)`) within `app/processor.py` that will be triggered by items on the "links_to_scrape" queue.
    - [x] Alternatively, if not using Huey tasks directly for consumption, implement a polling mechanism that dequeues from "links_to_scrape".
- [x] **Implement Link Downloading:**
    - [x] Inside the consumer task, implement logic to download the content from the given URL.
    - [x] Reuse or adapt existing scraping utilities from `app/scraping/` (e.g., `news_scraper`, `pdf_scraper`, `fallback_scraper` logic via `aggregator.py` if suitable) to get the raw content. This content will be temporary.
- [x] **Implement LLM Processing:**
    - [x] Integrate with `app/llm.py` to process the downloaded content.
    - [x] Implement specific error handling for LLM 429 errors: if a 429 status is received, the link (URL) should be re-added to the "links_to_scrape" queue for another consumer to try later. This might involve creating a new Huey task call or using Huey's retry mechanism with custom logic.
- [x] **Implement Article Creation:**
    - [x] After successful download and LLM processing (summarization, keyword extraction, etc.), create an `Articles` record in the database.
    - [x] Create associated `Summaries` records.
    - [x] Ensure the article status is set appropriately (e.g., `processed`).
- [x] **Integrate Processor into Application Lifecycle:**
    - [x] Ensure the Huey consumer for `app/processor.py` tasks is started when the application runs (e.g., via a Huey consumer process).
- [x] **Update `ai-memory/TASKS.md`** with key learnings, decisions, pivots, or any unresolved issues from this Phase before proceeding to the next.

**Reference Files:**
- `app/llm.py`
- `app/models.py`
- `app/database.py`
- `app/scraping/aggregator.py` (and individual scrapers for content fetching logic)
- `app/queue.py`

**Key Learnings/Decisions from this Phase:**
- **Processor Architecture:** Created `app/processor.py` as a standalone module with clear separation of concerns: duplicate checking, content downloading, LLM processing, and database operations.
- **Content Handling:** Implemented temporary content processing without storing raw_content in the database. Content is downloaded, processed, and discarded after creating summaries.
- **LLM Integration:** Successfully integrated with existing `app/llm.py` functions (`filter_article`, `summarize_article`, `summarize_pdf`) with proper error handling.
- **429 Rate Limit Handling:** Implemented specific error handling for LLM 429 rate limit errors using Huey's retry mechanism. The task will automatically retry with exponential backoff.
- **PDF Detection:** Added automatic PDF content detection using base64 decoding to determine content type and route to appropriate LLM functions.
- **Duplicate Prevention:** Implemented URL duplicate checking to avoid reprocessing existing articles.
- **Error Resilience:** Added comprehensive error handling at each step (download, LLM processing, database operations) with proper logging.
- **Queue Integration:** Successfully integrated the processor with the existing Huey queue system by updating `process_link_task` to call the processor functions.

## Phase 3: Database Model Changes and Content Handling

**Phase Goal:** Modify the database model to remove permanent `raw_content` storage and update all related code.

**Tasks:**
- [x] **Modify `app/models.py`:**
    - [x] Remove the `raw_content` field from the `Articles` model.
    - [x] Analyze if any other fields related to raw content processing need adjustment.
- [x] **Update Database Schema:**
    - [x] Plan for schema migration. If using Alembic, create a migration script. If not, document the manual SQL changes needed.
- [x] **Refactor Code Relying on `raw_content`:**
    - [x] Identify all parts of the codebase that currently read from or write to `Articles.raw_content`.
    - [x] The primary place will be the existing `summarize_task` in `app/queue.py`, which will likely be superseded by the new processor logic.
    - [x] Ensure the new `app/processor.py` handles raw content temporarily and does not attempt to save it to the `Articles` model.
- [x] **Update `ai-memory/TASKS.md`** with key learnings, decisions, pivots, or any unresolved issues from this Phase before proceeding to the next.

**Reference Files:**
- `app/models.py`
- `app/queue.py` (specifically `summarize_task`)
- Any other files that might interact with `Articles.raw_content`.

**Key Learnings/Decisions from this Phase:**
- **Database Model Simplification:** Successfully removed the `raw_content` field from the `Articles` model, reducing storage requirements and simplifying the data model.
- **Schema Migration Strategy:** Since the project doesn't use Alembic, documented that manual SQL migration would be needed: `ALTER TABLE articles DROP COLUMN raw_content;`
- **Code Refactoring:** Identified and removed all references to `raw_content` in the codebase, including `cron/process_articles.py` which was using the old direct processing approach.
- **Legacy Code Impact:** The `summarize_task` in `app/queue.py` still references `raw_content` parameters but this will be addressed in Phase 4 as it's now superseded by the new processor.
- **Processor Validation:** Confirmed that `app/processor.py` correctly handles content temporarily without attempting to store it in the database.
- **Backward Compatibility:** The removal of `raw_content` is a breaking change for existing databases, but aligns with the new architecture where content is processed immediately and not stored.

## Phase 4: Integration, Refactoring, and Testing

**Phase Goal:** Integrate the new system, refactor old components, and ensure everything is tested.

**Tasks:**
- [ ] **Review and Refactor `app/queue.py`:**
    - [ ] The existing `summarize_task` in `app/queue.py` is likely redundant now that `app/processor.py` handles LLM processing.
    - [ ] Decide whether to remove `summarize_task` entirely or adapt it if it serves any other purpose.
- [ ] **Update Cron Jobs:**
    - [ ] Modify `cron/run_full_pipeline.py` and `cron/process_articles.py` (and any other relevant cron scripts) to align with the new queue-based processing flow. They should primarily focus on populating the "links_to_scrape" queue, and the new processor will handle the rest.
- [ ] **Testing:**
    - [ ] Write unit tests for the new queue tasks in `app/queue.py`.
    - [ ] Write unit/integration tests for `app/processor.py`, covering:
        - Link downloading.
        - LLM processing (mocking the LLM service).
        - Retry logic for 429 errors.
        - Article and Summary creation.
    - [ ] Test modifications to `hackernews_scraper.py` and `reddit.py` to ensure they correctly add links to the queue.
    - [ ] Perform end-to-end testing of the new pipeline.
- [ ] **Update `ai-memory/TASKS.md`** with key learnings, decisions, pivots, or any unresolved issues from this Phase before proceeding to the next.

**Reference Files:**
- `app/queue.py`
- `cron/run_full_pipeline.py`
- `cron/process_articles.py`
- Test files.

**Key Learnings/Decisions from this Phase:**
- (To be filled at end of Phase)

## Phase 5: Documentation Update

**Phase Goal:** Update project documentation to reflect the architectural changes.

**Tasks:**
- [ ] **Update `ai-memory/README.md`:**
    - [ ] Revise the "System Patterns" section, especially the application architecture diagram and descriptions related to scraping, queueing, and content processing.
    - [ ] Document the new `app/processor.py` and its role.
    - [ ] Reflect the removal of `raw_content` from the `Articles` model.
- [ ] **Final Review of `ai-memory/TASKS.md`:**
    - [ ] Ensure all tasks are marked complete.
    - [ ] Fill in all "Key Learnings/Decisions from this Phase" sections.
- [ ] **Update `ai-memory/TASKS.md`** with key learnings, decisions, pivots, or any unresolved issues from this Phase before proceeding to the next.

**Reference Files:**
- `ai-memory/README.md`

**Key Learnings/Decisions from this Phase:**
- (To be filled at end of Phase)
