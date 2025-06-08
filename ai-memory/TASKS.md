# Substack RSS Downloader Implementation Plan

## Phase 1: Database and Configuration

- [ ] **Database Migration**:
    - [ ] Add a `local_path` column (nullable `String`) to the `Articles` model in `app/models.py`. This will store the path to the downloaded Substack article markdown file.
    - [ ] Generate and apply an Alembic migration script to update the database schema.
- [ ] **Configuration**:
    - [ ] Verify that `feedparser` and `PyYAML` are in `pyproject.toml`. (Already confirmed).
    - [ ] Use the existing `config/substack.yml` for feed URLs.

## Phase 2: Scraper Implementation

- [ ] **Create Scraper File**: Create a new file `app/scraping/substack_scraper.py`.
- [ ] **Implement `SubstackScraper`**:
    - [ ] Create a `SubstackScraper` class.
    - [ ] Implement a method to load feed URLs from `config/substack.yml`.
    - [ ] For each feed, use `feedparser` to fetch and parse the RSS data.
    - [ ] Implement a regex filter to exclude entries that appear to be podcasts (e.g., containing "podcast" or "transcript" in the title).
    - [ ] For each valid article entry:
        - [ ] Extract the title, link, publication date, and the full HTML content from `content:encoded`.
        - [ ] Sanitize the title to create a filesystem-safe filename (e.g., `import-ai-412-amazons-sorting-robot.md`).
        - [ ] Ensure the `data/substack/` directory exists.
        - [ ] Save the HTML content to the markdown file: `data/substack/{sanitized-filename}`.
        - [ ] Use the existing `create_link_record` pattern from the HackerNews scraper to add a new entry to the `links` table with `source='substack'`.
        - [ ] The key difference: when the article is processed and an `Article` record is created, the `local_path` will be populated.

## Phase 3: Local Article Processor

- [ ] **Create Processor Script**: Create a new file `scripts/process_local_articles.py`.
- [ ] **Implement Local Processor Logic**:
    - [ ] The script will query the database for `Articles` with `status = 'new'` and a non-null `local_path`.
    - [ ] For each article found:
        - [ ] Read the HTML content from the file specified in `local_path`.
        - [ ] Use `trafilatura` or a similar library to extract the main text content from the HTML.
        - [ ] Pass the cleaned text to the `llm.summarize_article` function.
        - [ ] If summarization is successful, update the `Article` record with the short and detailed summaries and set its `status` to `processed`.
        - [ ] If summarization fails, update the `Article` record's `status` to `failed`.
- [ ] **No Strategy Needed**: This approach bypasses the URL-based strategy factory, as the content is already local.

## Phase 4: Integration and Testing

- [ ] **Update `run_scrapers.py`**:
    - [ ] Import and call the new `SubstackScraper` within the main execution flow of `scripts/run_scrapers.py`.
- [ ] **Write Unit Tests**:
    - [ ] Create `tests/scraping/test_substack_scraper.py` to test feed parsing, filtering, and file creation.
    - [ ] Create `tests/processing_strategies/test_substack_strategy.py` to test reading from a local file and preparing data for the LLM.
- [ ] **Write Integration Test**:
    - [ ] Create an end-to-end test to verify the full flow: scraping a mock RSS feed, creating a link, saving the file, processing the link, summarizing the content, and storing it in the database.
- [ ] **Run Tests**:
    - [ ] Execute all tests via `pytest` to ensure correctness and avoid regressions.

## Phase 5: Documentation

- [ ] **Update `ai-memory/README.md`**:
    - [ ] Document the new `SubstackScraper` and `SubstackStrategy`.
    - [ ] Explain the role of the `local_path` column in the `Articles` table.
    - [ ] Mention the `data/substack/` directory for storing downloaded content.
