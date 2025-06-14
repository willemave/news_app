# News Aggregation & Summarization App

## Purpose

* Aggregate news from web sites, RSS feeds, PDFs, Reddit, and other sources
* Auto-scrape, filter with LLM, generate short + detailed summaries, store, and display in web UI
* Provide intelligent content filtering based on user preferences (tech, AI, business strategy)
* Enable fast scanning via AI-generated summaries with admin pipeline visibility

## Core Architecture

### Unified Content Model
* **Content Model**: Single [`Content`](app/models/schema.py:24) model handles both articles and podcasts via `content_type` field
* **Status Tracking**: [`ContentStatus`](app/models/schema.py:17) enum tracks pipeline state (new, processing, completed, failed, skipped)
* **Metadata Storage**: JSON field stores type-specific data (article content, podcast transcripts, etc.)
* **Processing Queue**: [`ProcessingTask`](app/models/schema.py:59) replaces Huey for task management

### Strategy Pattern Processing
* **URL Processing**: Strategy pattern via [`UrlProcessorFactory`](app/processing_strategies/factory.py:17) handles different content types
* **Strategies**: [`HtmlProcessorStrategy`](app/processing_strategies/html_strategy.py), [`PdfProcessorStrategy`](app/processing_strategies/pdf_strategy.py), [`PubMedProcessorStrategy`](app/processing_strategies/pubmed_strategy.py), [`ArxivProcessorStrategy`](app/processing_strategies/arxiv_strategy.py), [`ImageProcessorStrategy`](app/processing_strategies/image_strategy.py)
* **HTTP Client**: [`RobustHttpClient`](app/http_client/robust_http_client.py) with retry logic and rate limiting

### API & UI
* **FastAPI**: [`main.py`](app/main.py:15) with routers for [`articles`](app/routers/articles.py), [`podcasts`](app/routers/podcasts.py), [`admin`](app/routers/admin.py)
* **Templates**: Jinja2 with markdown filter support, HTMX for dynamic actions
* **Static**: TailwindCSS for styling

### Data Layer
* **Unified Model**: [`Content`](app/models/schema.py:24) for all content types (articles, podcasts)
* **Task Queue**: [`ProcessingTask`](app/models/schema.py:59) for background job management
* **Enums**: [`ContentType`](app/models/schema.py:13), [`ContentStatus`](app/models/schema.py:17) for type safety
* **Database**: SQLite/PostgreSQL via SQLAlchemy with JSON metadata support

### LLM Integration
* **Provider Abstraction**: [`LLMService`](app/services/llm.py:70) with pluggable providers
* **Providers**: [`OpenAIProvider`](app/services/llm.py:26), [`MockProvider`](app/services/llm.py:58) for testing
* **Functions**: [`summarize_content()`](app/services/llm.py:85), [`extract_topics()`](app/services/llm.py:120)
* **Error Handling**: Robust JSON parsing with fallback for malformed responses

### Queue System
* **Database-Backed Queue**: [`QueueService`](app/services/queue.py:27) replaces Huey with simple SQLite/PostgreSQL queue
* **Task Types**: [`TaskType`](app/services/queue.py:14) enum (scrape, process_content, download_audio, transcribe, summarize)
* **Worker Pool**: [`TaskProcessorPool`](app/pipeline/task_processor.py:283) manages concurrent workers
* **Retry Logic**: Automatic retry with exponential backoff

### Error Logging
* **Generic Error Logger**: [`GenericErrorLogger`](app/utils/error_logger.py:29) replaced complex RSS-specific logger
* **Context Capture**: Full HTTP responses, stack traces, operation context
* **Structured Logs**: JSON Lines format for easy parsing and analysis
* **Factory Function**: [`create_error_logger()`](app/utils/error_logger.py:205) for component-specific loggers

## Tech Stack

* **Core**: Python 3.13, FastAPI, SQLAlchemy, Pydantic v2, SQLite/PostgreSQL
* **Content Processing**: trafilatura, PyPDF2, feedparser, beautifulsoup4
* **LLM**: google-genai (Gemini), openai (optional), httpx for HTTP
* **Queue**: Database-backed queue (replaced Huey)
* **Transcription**: faster-whisper for podcast processing
* **Frontend**: Jinja2, TailwindCSS, HTMX
* **Testing**: pytest, pytest-asyncio, pytest-mock, pytest-cov
* **Development**: ruff (linting), uv (package management)

## Key Workflows

1. **Content Ingestion**: Scrapers add items to [`Content`](app/models/schema.py:24) table with `status=new`
2. **Task Creation**: [`QueueService`](app/services/queue.py:27) creates processing tasks
3. **Worker Processing**: [`ContentWorker`](app/pipeline/worker.py:23) processes content by type
4. **Article Pipeline**: Download → Extract → LLM Filter → Summarize → Store
5. **Podcast Pipeline**: Download Audio → Transcribe → Summarize → Store
6. **Web UI**: Display content with filtering, admin dashboard for pipeline monitoring

## Key Repository Folders and Files

### Core Application
* [`app/main.py`](app/main.py) - FastAPI application entry point
* [`app/models/schema.py`](app/models/schema.py) - Unified content and task models
* [`app/core/settings.py`](app/core/settings.py) - Pydantic settings management
* [`app/core/db.py`](app/core/db.py) - Database connection management
* [`app/core/logging.py`](app/core/logging.py) - Centralized logging configuration

### Scrapers
* [`app/scraping/runner.py`](app/scraping/runner.py) - Manages and runs all scrapers
* [`app/scraping/hackernews_unified.py`](app/scraping/hackernews_unified.py) - HackerNews scraper
* [`app/scraping/reddit_unified.py`](app/scraping/reddit_unified.py) - Reddit scraper (multi-subreddit)
* [`app/scraping/substack_unified.py`](app/scraping/substack_unified.py) - RSS feed scraper for Substack
* [`app/scraping/podcast_unified.py`](app/scraping/podcast_unified.py) - Podcast RSS scraper

### Processing Pipeline
* [`app/pipeline/task_processor.py`](app/pipeline/task_processor.py) - Main task processing logic
* [`app/pipeline/worker.py`](app/pipeline/worker.py) - Content processing worker
* [`app/pipeline/checkout.py`](app/pipeline/checkout.py) - Content checkout management
* [`app/pipeline/podcast_workers.py`](app/pipeline/podcast_workers.py) - Podcast-specific workers

### Processing Strategies
* [`app/processing_strategies/factory.py`](app/processing_strategies/factory.py) - Strategy factory with registration
* [`app/processing_strategies/base_strategy.py`](app/processing_strategies/base_strategy.py) - Abstract base strategy
* [`app/processing_strategies/html_strategy.py`](app/processing_strategies/html_strategy.py) - HTML content processing
* [`app/processing_strategies/pdf_strategy.py`](app/processing_strategies/pdf_strategy.py) - PDF content processing
* [`app/processing_strategies/arxiv_strategy.py`](app/processing_strategies/arxiv_strategy.py) - ArXiv preprocessing
* [`app/processing_strategies/image_strategy.py`](app/processing_strategies/image_strategy.py) - Image processing
* [`app/processing_strategies/pubmed_strategy.py`](app/processing_strategies/pubmed_strategy.py) - PubMed delegation

### Services
* [`app/services/queue.py`](app/services/queue.py) - Database-backed task queue
* [`app/services/llm.py`](app/services/llm.py) - LLM service with provider abstraction
* [`app/services/http.py`](app/services/http.py) - HTTP service wrapper

### Domain Models
* [`app/domain/content.py`](app/domain/content.py) - Domain content models
* [`app/domain/converters.py`](app/domain/converters.py) - Convert between domain and DB models

### HTTP Client
* [`app/http_client/robust_http_client.py`](app/http_client/robust_http_client.py) - Async HTTP client with retry logic

### Utilities
* [`app/utils/error_logger.py`](app/utils/error_logger.py) - Generic error logging with context

### Web Interface
* [`app/routers/articles.py`](app/routers/articles.py) - Article viewing endpoints
* [`app/routers/podcasts.py`](app/routers/podcasts.py) - Podcast viewing endpoints
* [`app/routers/admin.py`](app/routers/admin.py) - Admin dashboard and controls
* [`app/api/content.py`](app/api/content.py) - Content API endpoints
* [`templates/`](templates/) - Jinja2 templates with markdown support
* [`static/`](static/) - TailwindCSS styles and JavaScript

### Scripts
* [`scripts/run_scrapers_unified.py`](scripts/run_scrapers_unified.py) - Run scrapers manually
* [`scripts/run_unified_pipeline.py`](scripts/run_unified_pipeline.py) - Run processing pipeline
* [`scripts/clear_database.py`](scripts/clear_database.py) - Database cleanup utility

### Configuration
* [`config/podcasts.yml`](config/podcasts.yml) - Podcast RSS feed URLs
* [`config/substack.yml`](config/substack.yml) - Substack RSS feed URLs
* [`pyproject.toml`](pyproject.toml) - Project dependencies and configuration
* [`.env.example`](.env.example) - Environment variable template

### Testing
* [`tests/`](tests/) - Comprehensive test suite
* [`tests/processing_strategies/`](tests/processing_strategies/) - Strategy pattern tests
* [`tests/pipeline/`](tests/pipeline/) - Pipeline processing tests
* [`tests/scraping/`](tests/scraping/) - Scraper tests
* [`tests/http_client/`](tests/http_client/) - HTTP client tests

## System Patterns

### Unified Content Architecture
* **Single Model**: All content types use same [`Content`](app/models/schema.py:24) model
* **Type Differentiation**: `content_type` field determines processing path
* **Flexible Metadata**: JSON field stores type-specific data
* **Status Tracking**: Consistent status management across all content

### Task Processing
* **Database Queue**: Simple, reliable task queue in same database
* **Worker Pool**: Concurrent workers with configurable pool size
* **Retry Logic**: Automatic retry with increasing delays
* **Task Types**: Specific task types for each processing stage

### Error Handling
* **Generic Logger**: [`GenericErrorLogger`](app/utils/error_logger.py:29) captures full context
* **Structured Logs**: JSON Lines format for easy parsing
* **Component Isolation**: Each component has its own error log
* **Context Preservation**: HTTP responses, stack traces, operation details

### Content Processing Pipeline
1. **Strategy Selection**: Factory pattern determines processor
2. **Content Download**: Robust HTTP client with retry
3. **Data Extraction**: Strategy-specific extraction
4. **LLM Processing**: Summarization with provider abstraction
5. **Database Storage**: Transactional updates with rollback

### Configuration Management
* **Environment Variables**: Settings via pydantic-settings
* **YAML Configuration**: External config for feeds
* **Type Safety**: Pydantic models for all settings

## Current Development Status

* **Implemented**: Unified content model replacing separate Article/Podcast models
* **Implemented**: Database-backed queue replacing Huey
* **Implemented**: Generic error logger replacing RSS-specific logger
* **Implemented**: LLM service abstraction with pluggable providers
* **Implemented**: Multi-scraper system with unified architecture
* **Implemented**: Strategy pattern for content processing
* **Implemented**: Comprehensive test suite
* **Implemented**: Admin dashboard with pipeline monitoring
* **In Progress**: Migration from old models to unified schema
* **Planned**: Additional LLM providers (Anthropic, local models)
* **Planned**: Enhanced content filtering and categorization