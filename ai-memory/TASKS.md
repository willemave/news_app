# Feature: Basic Logging Implementation

## Phase 1: Setup Basic Logging
- **Phase Goal:** Implement and document a basic logging setup for the application.
- **Tasks:**
  - [x] Add basic logging configuration to `app/config.py`.
  - [x] Update `ai-memory/README.md` to document the logging setup in the "Tech Context" section.
  - [x] Create this `ai-memory/TASKS.md` file and document the logging implementation tasks.
  - [x] Implement logging in `app/scraping/reddit.py` using the configured logger.
  - [x] Modify `app/scraping/reddit.py` in `fetch_reddit_posts` to use `reddit.front.best()` when `subreddit_name` is "front", ignoring `time_filter` for this case.
- **Reference Files:**
  - `app/config.py`
  - `ai-memory/README.md`
  - `app/scraping/reddit.py`
- **Key Learnings/Decisions from this Phase:**
  - Implemented a simple console logger using the `logging` module.
  - Configuration includes log level (INFO), format, and a stream handler.
  - Documentation added to `README.md` for future reference.
  - Updated Reddit scraper to use `front.best()` for the front page, which doesn't use `time_filter`.

## New Dependencies
- None
