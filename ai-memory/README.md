# News Aggregation & Summarization App

## Purpose

* Aggregate news from web sites, RSS feeds, PDFs, Reddit, Twitter, and other sources
* Auto-scrape, filter with LLM, generate short + detailed summaries, store, and display in web UI
* Provide intelligent content filtering based on user preferences (tech, AI, business strategy)
* Enable fast scanning via AI-generated summaries with admin pipeline visibility
* Support both article and podcast content with unified processing pipeline

## Core Architecture

### Unified Content Model
* **Content Model**: Single [`Content`](app/models/schema.py:24) model handles both articles and podcasts via `content_type` field
* **Status Tracking**: [`ContentStatus`](app/models/schema.py:17) enum tracks pipeline state (new, processing, completed, failed, skipped)
* **Metadata Storage**: JSON field stores type-specific data (article content, podcast transcripts, etc.)
* **Processing Queue**: [`ProcessingTask`](app/models/schema.py:59) replaces Huey for task management

### Strategy Pattern Processing
* **Strategy Registry**: [`StrategyRegistry`](app/processing_strategies/registry.py:13) manages content processing strategies with ordered precedence
* **Strategies**: 
  - [`ArxivProcessorStrategy`](app/processing_strategies/arxiv_strategy.py) - Handles arxiv.org/abs/ links
  - [`PubMedProcessorStrategy`](app/processing_strategies/pubmed_strategy.py) - Specific domain handling
  - [`PdfProcessorStrategy`](app/processing_strategies/pdf_strategy.py) - PDF content by extension/Content-Type
  - [`ImageProcessorStrategy`](app/processing_strategies/image_strategy.py) - Image file processing
  - [`HtmlProcessorStrategy`](app/processing_strategies/html_strategy.py) - HTML content with crawl4ai
* **HTTP Client**: [`RobustHttpClient`](app/http_client/robust_http_client.py) with retry logic and rate limiting

### API & UI
* **FastAPI**: [`main.py`](app/main.py:15) with routers for content, admin, logs, and API
* **Routers**: [`content`](app/routers/content.py), [`api_content`](app/routers/api_content.py), [`admin`](app/routers/admin.py), [`logs`](app/routers/logs.py)
* **Admin Prompt Tuning**: `/admin/prompt-tuning` view aggregates recent unliked content and surfaces LLM-generated summarization prompt revisions.
* **Templates**: Jinja2 with markdown filter support, HTMX for dynamic actions
* **Static**: TailwindCSS for styling

### Data Layer
* **Unified Model**: [`Content`](app/models/schema.py:24) for all content types (articles, podcasts) with classification support
* **Task Queue**: [`ProcessingTask`](app/models/schema.py:59) for background job management
* **Event Logging**: [`EventLog`](app/models/schema.py) for generic event tracking with JSON data
* **Enums**: [`ContentType`](app/models/metadata.py:14), [`ContentStatus`](app/models/metadata.py:19), [`ContentClassification`](app/models/metadata.py) for type safety
* **Database**: SQLite/PostgreSQL via SQLAlchemy with JSON metadata support
  - Database file: `news_app.db` (SQLite)
  - **Unique Constraint**: Composite unique index on `(url, content_type)` allows same URL for different content types (e.g., news item and article)
  - **Migration**: `alembic/versions/2e0429feeff5_allow_same_url_different_content_types.py` changed from single URL unique to composite
* **Schema Validation**: Pydantic models for metadata validation:
  - [`ArticleMetadata`](app/models/metadata.py:102) - Validates article-specific fields
  - [`PodcastMetadata`](app/models/metadata.py:148) - Validates podcast-specific fields
  - [`StructuredSummary`](app/models/metadata.py:47) - Structured summary format with bullet points and quotes
  - [`ContentData`](app/models/metadata.py:207) - Unified content data model for passing between layers
  - Automatic validation on metadata updates via validators

### LLM Integration
* **Google Flash Service**: [`GoogleFlashService`](app/services/google_flash.py:177) using Gemini 2.5 Flash Lite for summarization
* **Structured Output**: Uses Pydantic schema for guaranteed JSON structure
* **Functions**: 
  - [`summarize_content()`](app/services/google_flash.py:192) - Creates structured summaries with classification
  - Supports different prompts for articles vs podcasts
  - Articles get full markdown formatting, podcasts get transcript summaries
* **Structured Summaries**: 
  - Overview (50-100 words)
  - Categorized bullet points (configurable count)
  - Notable quotes (2-3 sentences each)
  - Topic tags (3-8 relevant tags)
  - Content classification (TO_READ/SKIP)
  - Full markdown for articles
* **Error Handling**: 
  - Robust JSON parsing with truncation repair
  - Comprehensive error logging to `logs/errors/llm_json_errors.log`
  - Handles MAX_TOKENS response truncation gracefully
* **JSON Repair Utility**: `app/utils/json_repair.py` provides shared cleanup and balancing for truncated JSON responses consumed by both OpenAI and Google providers

### Queue System
* **Database-Backed Queue**: [`QueueService`](app/services/queue.py:27) replaces Huey with simple SQLite/PostgreSQL queue
* **Task Types**: [`TaskType`](app/services/queue.py:14) enum (scrape, process_content, download_audio, transcribe, summarize)
* **Sequential Processor**: [`SequentialTaskProcessor`](app/pipeline/sequential_task_processor.py:22) processes tasks one at a time
  - Aggressive startup polling (10 polls at 100ms)
  - Adaptive backoff when queue is empty
  - Graceful shutdown with signal handling
* **Retry Logic**: Automatic retry with exponential backoff (max 3 retries by default)

### Error Logging
* **Generic Error Logger**: [`GenericErrorLogger`](app/utils/error_logger.py:29) replaced complex RSS-specific logger
* **Context Capture**: Full HTTP responses, stack traces, operation context
* **Structured Logs**: JSON Lines format for easy parsing and analysis
* **Factory Function**: [`create_error_logger()`](app/utils/error_logger.py:205) for component-specific loggers

## Tech Stack

* **Core**: Python 3.13, FastAPI, SQLAlchemy, Pydantic v2, SQLite/PostgreSQL
* **Content Processing**: trafilatura, PyPDF2, feedparser, beautifulsoup4, crawl4ai (0.7.4 with optional LLM table extraction toggle)
* **LLM**: google-genai (Gemini 2.5 Flash Lite), httpx for HTTP
* **Queue**: Database-backed queue (replaced Huey)
* **Transcription**: faster-whisper for podcast processing
* **Twitter Scraping**: Playwright (browser automation), jmespath (JSON processing)
* **Frontend**: Jinja2 with markdown filter, TailwindCSS, HTMX
* **Testing**: pytest, pytest-asyncio, pytest-mock, pytest-cov
* **Development**: ruff (linting), uv (package management)
* **Markdown**: Python-Markdown with extensions (extra, codehilite, toc, nl2br, smarty)

## Key Workflows

1. **Content Ingestion**: Scrapers add items to [`Content`](app/models/schema.py:24) table with `status=new`
2. **Task Creation**: [`QueueService`](app/services/queue.py:27) creates processing tasks
3. **Worker Processing**: [`ContentWorker`](app/pipeline/worker.py:24) processes content by type
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
* [`app/scraping/hackernews_unified.py`](app/scraping/hackernews_unified.py) - HackerNews scraper (emits `ContentType.NEWS` items but pipeline treats them like articles to pull the linked story)
* [`app/scraping/reddit_unified.py`](app/scraping/reddit_unified.py) - Reddit scraper (multi-subreddit)
* [`app/scraping/substack_unified.py`](app/scraping/substack_unified.py) - RSS feed scraper for Substack
* [`app/scraping/techmeme_unified.py`](app/scraping/techmeme_unified.py) - Dedicated Techmeme cluster scraper with aggregator metadata
* [`app/scraping/podcast_unified.py`](app/scraping/podcast_unified.py) - Podcast RSS scraper
* [`app/scraping/twitter_unified.py`](app/scraping/twitter_unified.py) - Twitter scraper (search-based aggregation); accepts authenticated cookies via `config/twitter.yml` → `client.cookies_path` (JSON or Netscape export) now that list timelines require login
* [`app/scraping/youtube_unified.py`](app/scraping/youtube_unified.py) - Unified YouTube channel scraper using yt-dlp

### Processing Pipeline
* [`app/pipeline/sequential_task_processor.py`](app/pipeline/sequential_task_processor.py) - Sequential task processor with adaptive polling
* [`app/pipeline/worker.py`](app/pipeline/worker.py) - Content processing worker with strategy pattern integration (NEWS items follow article flow unless marked aggregate)
* [`app/services/google_flash.py`](app/services/google_flash.py) - Handles LLM summarization; includes `news_digest` mode for quick key points
* [`app/scraping/techmeme_unified.py`](app/scraping/techmeme_unified.py) - Dedicated Techmeme cluster scraper emitting single-link news metadata
* [`app/scraping/twitter_unified.py`](app/scraping/twitter_unified.py) - Twitter list scraper splitting each external link into its own news item; requires cookies for 404-guarded list timelines and falls back to cookie-less mode with explicit warning
  - Lists now require authentication; configure `client.cookies_path` in `config/twitter.yml` with a JSON cookie export (`auth_token`, `ct0`) to enable scraping. Without cookies the scraper logs a warning and skips lists.
* [`app/pipeline/checkout.py`](app/pipeline/checkout.py) - Content checkout management for concurrent processing
* [`app/pipeline/podcast_workers.py`](app/pipeline/podcast_workers.py) - Podcast-specific workers (download, transcribe)

### Processing Strategies
* [`app/processing_strategies/registry.py`](app/processing_strategies/registry.py) - Global strategy registry with ordered registration
* [`app/processing_strategies/base_strategy.py`](app/processing_strategies/base_strategy.py) - Abstract base strategy interface
* [`app/processing_strategies/html_strategy.py`](app/processing_strategies/html_strategy.py) - HTML content processing with crawl4ai
* [`app/processing_strategies/pdf_strategy.py`](app/processing_strategies/pdf_strategy.py) - PDF content processing with PyPDF2
* [`app/processing_strategies/arxiv_strategy.py`](app/processing_strategies/arxiv_strategy.py) - ArXiv preprocessing (converts /abs/ to PDF)
* [`app/processing_strategies/image_strategy.py`](app/processing_strategies/image_strategy.py) - Image processing with LLM vision
* [`app/processing_strategies/pubmed_strategy.py`](app/processing_strategies/pubmed_strategy.py) - PubMed specific handling

### Services
* [`app/services/queue.py`](app/services/queue.py) - Database-backed task queue with atomic operations
* [`app/services/google_flash.py`](app/services/google_flash.py) - Google Gemini Flash service for summarization
* [`app/services/openai_llm.py`](app/services/openai_llm.py) - OpenAI service (optional, for transcription)
* [`app/services/http.py`](app/services/http.py) - HTTP service wrapper
* [`app/services/event_logger.py`](app/services/event_logger.py) - Generic event logging with timing and stats
* [`app/services/read_status.py`](app/services/read_status.py) - Read/unread status management
* [`app/services/favorites.py`](app/services/favorites.py) - Favorites toggle functionality
* [`app/services/prompt_tuning.py`](app/services/prompt_tuning.py) - Builds summarization prompt update suggestions from unliked content using Google Flash

### Domain Models
* [`app/models/metadata.py`](app/models/metadata.py) - Unified metadata models (merged from schemas/metadata.py and domain/content.py)
* [`app/domain/converters.py`](app/domain/converters.py) - Convert between domain ContentData and DB Content models

### Templates & Frontend
* [`app/templates.py`](app/templates.py) - Jinja2 configuration with markdown filter
* Templates directory structure:
  - `templates/` - Base templates with markdown rendering support
  - `templates/admin/` - Admin interface templates (missing logs templates)
  - `static/css/` - TailwindCSS styles (styles.css → app.css build)
  - `static/js/` - HTMX for dynamic interactions
  - `templates/admin_prompt_tuning.html` - Summarization prompt tuning dashboard

### HTTP Client
* [`app/http_client/robust_http_client.py`](app/http_client/robust_http_client.py) - Async HTTP client with retry logic

### Utilities
* [`app/utils/error_logger.py`](app/utils/error_logger.py) - Generic error logging with context
* [`app/utils/json_repair.py`](app/utils/json_repair.py) - Shared helpers to strip code fences and repair truncated LLM JSON payloads

### Web Interface
* [`app/main.py`](app/main.py) - FastAPI application entry point with middleware and router setup
* [`app/routers/content.py`](app/routers/content.py) - Unified content viewing endpoints
* [`app/routers/api_content.py`](app/routers/api_content.py) - RESTful API endpoints for content (iOS client integration)
* [`app/routers/admin.py`](app/routers/admin.py) - Admin dashboard with pipeline controls
* [`app/routers/logs.py`](app/routers/logs.py) - Log file viewer interface (templates missing)

### iOS Client
* [`client/newsly/newslyApp.swift`](client/newsly/newslyApp.swift) - App entry point
* [`client/newsly/ContentView.swift`](client/newsly/ContentView.swift) - Root TabView container
* [`client/newsly/Views/ArticlesView.swift`](client/newsly/Views/ArticlesView.swift) - Article list view
* [`client/newsly/Views/PodcastsView.swift`](client/newsly/Views/PodcastsView.swift) - Podcast list view
* [`client/newsly/Views/ContentDetailView.swift`](client/newsly/Views/ContentDetailView.swift) - Detail view with swipe navigation
* [`client/newsly/ViewModels/ContentListViewModel.swift`](client/newsly/ViewModels/ContentListViewModel.swift) - List state management
* [`client/newsly/Services/APIClient.swift`](client/newsly/Services/APIClient.swift) - Network layer
* [`client/newsly/Services/ContentService.swift`](client/newsly/Services/ContentService.swift) - Content API operations

### Scripts
* [`scripts/run_scrapers.py`](scripts/run_scrapers.py) - Run scrapers manually
* [`scripts/run_workers.py`](scripts/run_workers.py) - Run processing pipeline workers
* [`scripts/run_pending_tasks.py`](scripts/run_pending_tasks.py) - Process pending tasks
* [`scripts/mark_completed_structured_summary.py`](scripts/mark_completed_structured_summary.py) - Backfill completed status when structured summaries are present
* [`scripts/reset_content_processing.py`](scripts/reset_content_processing.py) - Reset content processing status
* [`scripts/resummarize_podcasts.py`](scripts/resummarize_podcasts.py) - Re-run summarization for podcasts
* [`scripts/retranscribe_podcasts.py`](scripts/retranscribe_podcasts.py) - Re-run transcription for podcasts
* [`scripts/test_youtube_scraper.py`](scripts/test_youtube_scraper.py) - Dry-run utility for individual YouTube channels
* [`scripts/dump_system_stats.py`](scripts/dump_system_stats.py) - CLI to emit aggregated database, queue, engagement, and event log statistics (table or JSON output)
* [`scripts/pretty_print_content.py`](scripts/pretty_print_content.py) - Pretty prints a specified content ID or random sample for a content type with structured summary metadata
* [`scripts/deploy/push_app.sh`](scripts/deploy/push_app.sh) - Deploys app to remote host and always mirrors `.env` from `.env.racknerd` via `sudo cp`
* [`scripts/deploy/push_envs.sh`](scripts/deploy/push_envs.sh) - Minimal helper to re-copy `.env.racknerd` to `.env` without rsync

### Configuration
* [`config/podcasts.yml`](config/podcasts.yml) - Podcast RSS feed URLs
* [`config/substack.yml`](config/substack.yml) - Substack RSS feed URLs with source names
* [`config/techmeme.yml`](config/techmeme.yml) - Techmeme feed settings (limit, related link toggles)
* [`config/reddit.yml`](config/reddit.yml) - Reddit subreddit configuration
* [`config/twitter.yml`](config/twitter.yml) - Twitter search queries and list configuration
* [`pyproject.toml`](pyproject.toml) - Project dependencies and configuration
* [`.env.example`](.env.example) - Environment variable template

### Testing
* [`tests/`](tests/) - Comprehensive test suite
* [`tests/processing_strategies/`](tests/processing_strategies/) - Strategy pattern tests
* [`tests/pipeline/`](tests/pipeline/) - Pipeline processing tests
* [`tests/scraping/`](tests/scraping/) - Scraper tests
* [`tests/http_client/`](tests/http_client/) - HTTP client tests

**Running Tests**:
* **CRITICAL**: Always set PYTHONPATH when running pytest to ensure correct module resolution:
  ```bash
  . .venv/bin/activate && PYTHONPATH=/Users/willem/Development/news_app pytest <test_path> -v
  ```
* For local development, the project root path should be set as PYTHONPATH
* Without PYTHONPATH, imports may fail or use wrong module paths

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

### Error Handling & Observability
* **Generic Logger**: [`GenericErrorLogger`](app/utils/error_logger.py:29) captures full context
* **Event Logger**: [`EventLogger`](app/services/event_logger.py) tracks system events in database
* **Structured Logs**: JSON Lines format for easy parsing
* **Component Isolation**: Each component has its own error log
* **Context Preservation**: HTTP responses, stack traces, operation details
* **Dual Logging**: File-based logs (viewable via admin) + database event logs

### Content Processing Pipeline
1. **Strategy Selection**: Registry pattern with ordered precedence checking
2. **Content Download**: Robust HTTP client with retry and rate limiting
3. **Data Extraction**: Strategy-specific extraction based on content type
4. **LLM Processing**: 
   - Articles: Full content summarization with markdown formatting
   - Podcasts: Transcript summarization without full markdown
   - News digests (Twitter/HackerNews/Techmeme): `news_digest` prompt returns title + link + concise key points without topics/full markdown
5. **Database Storage**: Transactional updates with JSON metadata validation

### Configuration Management
* **Environment Variables**: Settings via [`pydantic-settings`](app/core/settings.py)
* **YAML Configuration**: External config for feeds (config/*.yml)
* **Type Safety**: Pydantic models for all settings and configurations
* **Storage Overrides**: `MEDIA_BASE_DIR` (defaults to `<cwd>/data/media`) controls podcast/Substack media storage and exposes `settings.podcast_media_dir`; `LOGS_BASE_DIR` (defaults to `<cwd>/logs`) feeds `settings.logs_dir` for error logger + admin UI paths.
* **TailwindCSS Build**: `npx @tailwindcss/cli -i ./static/css/styles.css -o ./static/css/app.css`

## iOS Client Application

### Newsly iOS App
* **Location**: [`client/newsly/`](client/newsly/) - Native iOS SwiftUI application
* **Architecture**: MVVM pattern with SwiftUI and async/await networking
* **Navigation**: TabView with ArticlesView, PodcastsView, and SettingsView
* **API Integration**: Connects to FastAPI backend at `/api/content/` endpoints
* **Key Features**:
  - Content browsing with card-based list view
  - Filtering by content type and date
  - Read/unread status tracking with visual indicators
  - Favorites management
  - Pull-to-refresh support
  - Swipe navigation between articles in detail view
  - Long press Articles/Podcasts/News lists to bulk mark visible items as read (uses API bulk response metrics)
  - Settings view provides mark-all-as-read actions for articles, podcasts, and news content types
  - Responsive design for all iOS devices
* **Build Requirements**: iOS 15.0+, Swift 5.5+, Xcode
* **Critical Implementation Note**: When passing content to detail view, MUST pass full array of content IDs for swipe navigation

## API Endpoints

### Content API (`/api/content/`)
* **List Content**: `GET /api/content/` - Returns content with filters (type, date, read status)
* **Content Detail**: `GET /api/content/{id}` - Full content details with structured summary
* **Mark Read**: `POST /api/content/{id}/mark-read` - Mark single item as read
* **Mark Unread**: `DELETE /api/content/{id}/mark-unread` - Mark single item as unread
* **Bulk Mark Read**: `POST /api/content/bulk-mark-read` - Mark multiple items as read (now returns `marked_count`/`failed_ids` for long-press bulk actions)
* **Toggle Favorite**: `POST /api/content/{id}/toggle-favorite` - Toggle favorite status
* **ChatGPT URL**: `GET /api/content/{id}/chatgpt-url` - Generate ChatGPT chat URL for content
* **Convert to Article**: `POST /api/content/{id}/convert-to-article` - Convert news item to article for full processing (checks for existing article by URL+type)
* **Response Models**: Pydantic models with full OpenAPI documentation
  - [`ContentSummaryResponse`](app/routers/api_content.py:24) - List view summary
  - [`ContentDetailResponse`](app/routers/api_content.py:96) - Full content details
  - [`ContentListResponse`](app/routers/api_content.py:64) - List endpoint response
  - [`ConvertNewsResponse`](app/routers/api_content.py:1547) - News-to-article conversion response

## Current Development Status

* **Implemented**: Unified content model replacing separate Article/Podcast models
* **Implemented**: Database-backed queue replacing Huey
* **Implemented**: Generic error logger replacing RSS-specific logger
* **Implemented**: LLM service abstraction with pluggable providers
* **Implemented**: Multi-scraper system with unified architecture
* **Implemented**: Strategy pattern for content processing
* **Implemented**: Comprehensive test suite
* **Implemented**: Admin dashboard with pipeline monitoring
* **Implemented**: Pydantic schema validation for content metadata
* **Implemented**: Structured summarization with bullet points, quotes, and topics
* **Implemented**: Markdown rendering support in templates
* **Implemented**: Migration of domain models to app/models/metadata.py
* **Implemented**: Source tracking in metadata (substack name, podcast name, subreddit)
* **Implemented**: Strategy registry pattern for content processing
* **Implemented**: Enhanced error logging with JSON Lines format
* **Implemented**: Content classification system (TO_READ/SKIP)
* **Implemented**: Generic event logging system with timing and stats
* **Implemented**: Admin log file viewer interface (templates missing)
* **Implemented**: Google Gemini Flash integration with structured output
* **Implemented**: Markdown rendering in templates with multiple extensions
* **Implemented**: Sequential task processor with adaptive polling
* **Implemented**: Read status tracking with ContentReadStatus table
* **Implemented**: Favorites management with ContentFavorites table
* **Implemented**: Full-featured iOS client application with SwiftUI
* **Implemented**: RESTful API with OpenAPI documentation
* **Implemented**: Full markdown content storage for articles
* **Implemented**: Twitter scraper using Playwright to intercept GraphQL API calls for list aggregation
* **Implemented**: Standard logging for favorites/unlikes services using module loggers instead of prefixed print statements

## Container Build & Deployment

* **Multi-stage Dockerfiles**: `Dockerfile.server`, `Dockerfile.workers`, and `Dockerfile.scrapers` now share a common base layer that pre-installs Playwright system deps, `uv`, and use a builder stage to materialize the project `.venv` before copying minimal runtime assets.
* **Playwright assets**: Browser binaries are installed once in the builder stage (`PLAYWRIGHT_BROWSERS_PATH=/ms-playwright`) and copied into runtime images to avoid repeating downloads during rebuilds.
* **Build caching**: `uv sync` runs with BuildKit cache mounts for dependency wheels; Docker scripts default to `docker buildx build` with inline cache export so incremental rebuilds are nearly instant when code changes only.
* **Scripts updated**: `scripts/docker-build.sh` and `scripts/deploy-multi.sh` export `DOCKER_BUILDKIT=1` and leverage `buildx --cache-to type=inline` for consistent caching between local and remote builds.
* **Deploy env retention**: `scripts/deploy/push_app.sh` now hashes `uv.lock` and only removes the remote `.venv` when the lock contents change, letting deployments skip costly environment rebuilds when dependencies are unchanged.
