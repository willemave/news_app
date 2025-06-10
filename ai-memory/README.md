# News Aggregation & Summarization App

## Purpose

* Aggregate news from web sites, RSS feeds, PDFs, Reddit, and other sources
* Auto-scrape, filter with LLM, generate short + detailed summaries, store, and display in web UI
* Provide intelligent content filtering based on user preferences (tech, AI, business strategy)
* Enable fast scanning via AI-generated summaries with admin pipeline visibility

## Core Architecture

### Strategy Pattern Processing
* **URL Processing**: Strategy pattern via [`UrlProcessorFactory`](app/processing_strategies/factory.py:14) handles different content types
* **Strategies**: [`HtmlProcessorStrategy`](app/processing_strategies/html_strategy.py), [`PdfProcessorStrategy`](app/processing_strategies/pdf_strategy.py), [`PubMedProcessorStrategy`](app/processing_strategies/pubmed_strategy.py), [`ArxivProcessorStrategy`](app/processing_strategies/arxiv_strategy.py)
* **HTTP Client**: [`RobustHttpClient`](app/http_client/robust_http_client.py) with retry logic and rate limiting

### API & UI
* **FastAPI**: [`main.py`](app/main.py:10) with routers for [`articles`](app/routers/articles.py), [`podcasts`](app/routers/podcasts.py), [`admin`](app/routers/admin.py)
* **Templates**: Jinja2 with markdown filter support, HTMX for dynamic actions
* **Static**: TailwindCSS for styling

### Data Layer
* **Models**: [`Articles`](app/models.py:40), [`Links`](app/models.py:26), [`FailureLogs`](app/models.py:64), [`CronLogs`](app/models.py:77), [`PodcastEpisodes`](app/models.py:90), [`PodcastDownloads`](app/models.py:118)
* **Status Tracking**: [`LinkStatus`](app/models.py:8), [`ArticleStatus`](app/models.py:15), [`PodcastStatus`](app/models.py:21) enums for pipeline state
* **Database**: SQLite via SQLAlchemy with [`local_path`](app/models.py:62) support for Substack articles

### LLM Integration
* **Provider**: Google Gemini 2.5 Flash via [`llm.py`](app/llm.py:6)
* **Functions**: [`filter_article()`](app/llm.py:126), [`summarize_article()`](app/llm.py:188), [`summarize_pdf()`](app/llm.py:254)
* **Error Handling**: Robust JSON parsing with fallback for malformed responses

### Queue System
* **Background Processing**: Huey with SQLite backend via [`queue.py`](app/queue.py:15)
* **Tasks**: [`process_link_task()`](app/queue.py:18) with retry logic for rate limits
* **Utilities**: [`drain_queue()`](app/queue.py:143), [`get_queue_stats()`](app/queue.py:173)

## Tech Stack

* **Core**: Python 3.13, FastAPI, SQLAlchemy, Pydantic v2, SQLite
* **Content Processing**: trafilatura, PyPDF2, feedparser, beautifulsoup4
* **LLM**: google-genai, httpx for HTTP
* **Queue**: Huey with SQLite backend
* **Frontend**: Jinja2, TailwindCSS, HTMX
* **Testing**: pytest, pytest-asyncio, pytest-mock, pytest-cov
* **Development**: ruff (linting), uv (package management)

## Key Workflows

1. **Link Ingestion**: Scrapers add URLs to [`Links`](app/models.py:26) table with `status=new`
2. **Background Processing**: [`process_link_task()`](app/queue.py:18) downloads content using strategy pattern
3. **LLM Filtering**: [`filter_article()`](app/llm.py:126) determines relevance based on preferences
4. **Summarization**: [`summarize_article()`](app/llm.py:188) or [`summarize_pdf()`](app/llm.py:254) creates summaries
5. **Storage**: Creates [`Articles`](app/models.py:40) record with summaries, updates link status
6. **Web UI**: Display articles with filtering, admin dashboard for pipeline monitoring

## Key Repository Folders and Files

### Core Application
* [`app/main.py`](app/main.py) - FastAPI application entry point
* [`app/models.py`](app/models.py) - SQLAlchemy models with status enums
* [`app/processor.py`](app/processor.py) - Main processing logic with strategy pattern
* [`app/llm.py`](app/llm.py) - Google Gemini integration for filtering and summarization
* [`app/queue.py`](app/queue.py) - Huey background task management
* [`app/schemas.py`](app/schemas.py) - Pydantic models for API/validation

### Processing Strategies
* [`app/processing_strategies/factory.py`](app/processing_strategies/factory.py) - Strategy factory with registration
* [`app/processing_strategies/base_strategy.py`](app/processing_strategies/base_strategy.py) - Abstract base strategy
* [`app/processing_strategies/html_strategy.py`](app/processing_strategies/html_strategy.py) - HTML content processing
* [`app/processing_strategies/pdf_strategy.py`](app/processing_strategies/pdf_strategy.py) - PDF content processing
* [`app/processing_strategies/pubmed_strategy.py`](app/processing_strategies/pubmed_strategy.py) - PubMed delegation strategy
* [`app/processing_strategies/arxiv_strategy.py`](app/processing_strategies/arxiv_strategy.py) - ArXiv preprocessing strategy
* [`app/processing_strategies/image_strategy.py`](app/processing_strategies/image_strategy.py) - Image processing strategy

### Podcast Pipeline
* [`app/podcast/pipeline_orchestrator.py`](app/podcast/pipeline_orchestrator.py) - Orchestrates the podcast processing pipeline
* [`app/podcast/podcast_downloader.py`](app/podcast/podcast_downloader.py) - Downloads podcast episodes
* [`app/podcast/podcast_converter.py`](app/podcast/podcast_converter.py) - Converts audio files to a standard format
* [`app/podcast/podcast_summarizer.py`](app/podcast/podcast_summarizer.py) - Summarizes podcast episodes using LLM
* [`app/podcast/state_machine.py`](app/podcast/state_machine.py) - Manages the state of podcast episodes

### Scrapers
* [`app/scraping/hackernews_scraper.py`](app/scraping/hackernews_scraper.py) - HackerNews top stories
* [`app/scraping/reddit.py`](app/scraping/reddit.py) - Reddit front page scraper
* [`app/scraping/substack_scraper.py`](app/scraping/substack_scraper.py) - RSS feed scraper for Substack
* [`app/scraping/podcast_rss_scraper.py`](app/scraping/podcast_rss_scraper.py) - Scrapes podcast RSS feeds

### HTTP Client
* [`app/http_client/robust_http_client.py`](app/http_client/robust_http_client.py) - Async HTTP client with retry logic

### Utilities
* [`app/utils/failures.py`](app/utils/failures.py) - Failure logging utilities

### Web Interface
* [`app/routers/articles.py`](app/routers/articles.py) - Article viewing endpoints
* [`app/routers/podcasts.py`](app/routers/podcasts.py) - Podcast viewing endpoints with filtering
* [`app/routers/admin.py`](app/routers/admin.py) - Admin dashboard and controls
* [`templates/`](templates/) - Jinja2 templates with markdown support
* [`static/`](static/) - TailwindCSS styles and JavaScript

### Automation
* [`cron/run_scrapers_job.py`](cron/run_scrapers_job.py) - Scheduled scraping job

### Configuration
* [`config/substack.yml`](config/substack.yml) - Substack RSS feed URLs
* [`pyproject.toml`](pyproject.toml) - Project dependencies and configuration

### Testing
* [`tests/`](tests/) - Comprehensive test suite mirroring app structure
* [`tests/processing_strategies/`](tests/processing_strategies/) - Strategy pattern tests
* [`tests/http_client/`](tests/http_client/) - HTTP client tests
* [`tests/scraping/`](tests/scraping/) - Scraper tests

### Scripts & Utilities
* [`scripts/run_scrapers.py`](scripts/run_scrapers.py) - Manual scraper execution
* [`scripts/process_local_articles.py`](scripts/process_local_articles.py) - Local content processing
* [`scripts/migrations/`](scripts/migrations/) - Database migration scripts
* [`scripts/clear_database.py`](scripts/clear_database.py) - Database cleanup utility

## System Patterns

### Error Handling
* **Failure Logging**: [`record_failure()`](app/utils/failures.py:10) with phase tracking
* **Status Management**: Comprehensive status enums for links and articles
* **Retry Logic**: Huey task retries for rate limits and transient failures
* **Graceful Degradation**: Fallback parsing for malformed LLM responses

### Content Processing Pipeline
1. **URL Strategy Selection**: Factory pattern determines appropriate processor
2. **Content Download**: Robust HTTP client with retry and rate limiting
3. **Data Extraction**: Strategy-specific extraction (HTML, PDF, delegation)
4. **Duplicate Detection**: URL checking at multiple pipeline stages
5. **LLM Processing**: Filtering and summarization with error handling
6. **Database Storage**: Transactional updates with rollback support

### Configuration Management
* **Environment Variables**: Settings via pydantic-settings
* **YAML Configuration**: External config files for scrapers
* **Database Paths**: Configurable SQLite and Huey database locations

## Current Development Status

* **Implemented**: Core processing pipeline with strategy pattern
* **Implemented**: HackerNews, Reddit, and Substack scrapers
* **Implemented**: Google Gemini LLM integration with robust error handling
* **Implemented**: Comprehensive test suite 
* **Implemented**: Admin dashboard with pipeline monitoring
* **Implemented**: Podcast processing continuation - existing podcasts now continue through pipeline instead of being skipped
* **Implemented**: Podcast download date filtering - dropdown filter showing actual download dates from database
* **Implemented**: Substack RSS processing with local file storag