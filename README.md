# Newsly - Intelligent News Aggregation Platform

An AI-powered news aggregation and summarization platform that intelligently collects, processes, and delivers content from multiple sources. Built with FastAPI and native iOS app, powered by Google Gemini for intelligent content analysis.

## 🚀 Key Features

### Content Aggregation
- **Multi-Source Collection**: Scrapes from HackerNews, Reddit, Substack RSS, and podcast feeds
- **Smart Processing Pipeline**: Parallel content extraction with retry logic and error recovery
- **Unified Content Model**: Single architecture handles articles, podcasts, videos, and PDFs
- **Strategy Pattern**: Pluggable processors for HTML, PDF, ArXiv papers, images, YouTube videos

### AI-Powered Intelligence
- **Google Gemini Integration**: Uses Gemini 2.5 Flash for rapid content summarization
- **Smart Classification**: Automatic TO_READ/SKIP categorization based on content relevance
- **Structured Summaries**: Consistent JSON output with key points and metadata
- **Podcast Transcription**: Local Whisper model or OpenAI API for audio processing

### User Experience
- **Native iOS App**: SwiftUI client with full API integration
- **Web Interface**: HTMX-powered responsive UI with real-time updates
- **Favorites System**: Save and organize important content
- **Read Status Tracking**: Personal reading history and progress
- **Advanced Filtering**: Search by platform, status, date, and classification

### Platform Features
- **Admin Dashboard**: Real-time pipeline monitoring and control
- **Task Queue System**: Database-backed sequential processing with status tracking
- **Comprehensive Logging**: Structured error tracking with full context
- **RESTful API**: Complete JSON API for third-party integrations

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Clients                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   iOS App    │  │  Web (HTMX)  │  │   API/CLI    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Application                       │
│  ┌──────────────────────────────────────────────────┐      │
│  │            Routers & API Endpoints                │      │
│  └──────────────────────────────────────────────────┘      │
│  ┌──────────────────────────────────────────────────┐      │
│  │              Services Layer                       │      │
│  │  (Business Logic, LLM Integration, Favorites)    │      │
│  └──────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                   Processing Pipeline                        │
│  ┌───────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │ Scrapers  │→ │ Task Queue   │→ │  Strategies  │        │
│  └───────────┘  └──────────────┘  └──────────────┘        │
│                                           │                  │
│                                    ┌──────────────┐         │
│                                    │  LLM Service │         │
│                                    └──────────────┘         │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                     Data Layer                               │
│  ┌──────────────────────────────────────────────────┐      │
│  │     SQLAlchemy ORM + Alembic Migrations          │      │
│  └──────────────────────────────────────────────────┘      │
│  ┌──────────────────────────────────────────────────┐      │
│  │        SQLite (dev) / PostgreSQL (prod)          │      │
│  └──────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

## 💻 Technology Stack

### Backend
- **Python 3.13** - Latest Python with full type hints
- **FastAPI** - High-performance async web framework
- **SQLAlchemy 2.0** - Modern ORM with async support
- **Pydantic v2** - Data validation and serialization
- **Alembic** - Database migrations

### AI/ML
- **Google Gemini 2.5 Flash** - Primary LLM for summarization
- **Whisper (faster-whisper)** - Local podcast transcription
- **OpenAI API** - Alternative transcription service

### Content Processing
- **crawl4ai** - Advanced web scraping with JS support
- **trafilatura** - Article text extraction
- **beautifulsoup4** - HTML parsing
- **feedparser** - RSS/Atom feed parsing
- **PyPDF2** - PDF text extraction
- **Pillow** - Image processing

### Frontend
- **SwiftUI** - Native iOS application
- **HTMX** - Dynamic web UI without heavy JS
- **Jinja2** - Server-side templating
- **TailwindCSS** - Utility-first CSS
- **Python-Markdown** - Rich text rendering

### Infrastructure
- **uv** - Ultra-fast Python package management
- **ruff** - Lightning-fast Python linter
- **pytest** - Comprehensive testing
- **Docker** - Container deployment (optional)

## 📱 iOS Client

Native SwiftUI application with:
- Content browsing by type (articles/podcasts)
- Detailed view with markdown rendering
- Favorites management
- Read status synchronization
- Pull-to-refresh
- Settings and API configuration
- Sources management via drill-down screens:
  - Feed Sources (Substack/Atom/YouTube) using `/api/scrapers?types=substack,atom,youtube`
  - Podcast Sources using `/api/scrapers?type=podcast_rss` with optional `limit` (1–100, default 10)

## 🚀 Quick Start

### Prerequisites
- Python 3.13+
- Node.js 18+ (for TailwindCSS)
- SQLite or PostgreSQL
- Google API key for Gemini

### Installation

1. **Clone and setup environment**
```bash
git clone <repository-url>
cd news_app

# Install uv if not present
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment
uv venv
source .venv/bin/activate
```

2. **Install dependencies**
```bash
uv sync
npm install  # For TailwindCSS
```

3. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your settings:
# - GOOGLE_API_KEY (required)
# - DATABASE_URL (optional)
# - OPENAI_API_KEY (optional)
```

4. **Initialize database**
```bash
alembic upgrade head
```

5. **Build frontend assets**
```bash
npx @tailwindcss/cli -i ./static/css/styles.css -o ./static/css/app.css --watch
```

6. **Run application**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

## 📖 Usage Guide

### Web Interface
- **Home** (`/`) - All content with filtering
- **Articles** (`/articles`) - Article-only view
- **Podcasts** (`/podcasts`) - Podcast-only view
- **Favorites** (`/favorites`) - Saved content
- **Admin** (`/admin`) - Pipeline monitoring
- **API Docs** (`/docs`) - Interactive API documentation

### Content Collection
```bash
# Run all scrapers
python scripts/run_scrapers.py

# Run specific scrapers
python scripts/run_scrapers.py --scrapers hackernews reddit

# Start processing pipeline
python scripts/run_workers.py --max-workers 2
```

### Configuration Files
- `config/substack.yml` - Newsletter RSS feeds
- `config/podcasts.yml` - Podcast RSS feeds
- `config/reddit.yml` - Subreddit configuration

## 🔧 Development

### Project Structure
```
news_app/
├── app/                        # Main application
│   ├── core/                  # Core utilities
│   ├── models/                # Database models
│   ├── routers/               # API endpoints
│   ├── services/              # Business logic
│   ├── pipeline/              # Processing pipeline
│   ├── processing_strategies/ # Content handlers
│   ├── scraping/              # Content scrapers
│   └── templates/             # HTML templates
├── client/                    # Client applications
│   └── newsly/               # iOS app (SwiftUI)
├── scripts/                   # Utility scripts
├── tests/                     # Test suite
├── config/                    # Feed configurations
├── alembic/                   # DB migrations
└── static/                    # CSS/JS assets
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific tests
pytest tests/services/ -v
```

### Code Quality
```bash
# Format code
ruff format

# Lint
ruff check

# Type checking
mypy app
```

> **Workflow requirement:** After every set of edits, run `ruff check` (without `--fix`) from the repository root, resolve every reported issue, and only then push changes.

### Scraper Configuration & Guest Tokens
- Set `NEWSAPP_CONFIG_DIR` to point at your config directory (defaults to `config/`).
- Copy the provided examples (`config/reddit.example.yml`, `config/substack.example.yml`, `config/podcasts.example.yml`) into that directory and rename them to `*.yml` before running scrapers.
- The Twitter scraper automatically activates an X guest token when cookies are not supplied. Structured warning logs include status, content type, retryability, and preview fields for troubleshooting.
- To verify headers locally, run `python3 scripts/run_scrapers.py --scrapers twitter --debug` after exporting the required configs or simulate a dry-run with a small harness that calls `TwitterUnifiedScraper()._decode_response_json(...)`.

### Database Operations
```bash
# Create migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## 📚 API Reference

### Content Endpoints
- `GET /api/content` - List content with filtering
- `GET /api/content/{id}` - Get content details
- `POST /api/content/{id}/read` - Mark as read
- `POST /api/content/{id}/unread` - Mark as unread
- `POST /api/content/{id}/favorite` - Add to favorites
- `DELETE /api/content/{id}/favorite` - Remove from favorites

### Admin Endpoints
- `GET /api/admin/stats` - System statistics
- `GET /api/admin/tasks` - Task queue status
- `POST /api/admin/tasks/retry` - Retry failed tasks

## 🛠️ Scripts

### Content Management
- `run_scrapers.py` - Execute content scrapers
- `run_workers.py` - Start processing workers
- `run_pending_tasks.py` - Process specific tasks
- `reset_content_processing.py` - Reset content status
- `resummarize_podcasts.py` - Re-run podcast summaries

### Maintenance
- `populate_publication_dates.py` - Backfill dates
- `reset_errored_content.py` - Clear error states
- `check_content.py` - Verify content integrity

## 🔒 Security

- Environment-based configuration
- SQL injection prevention via ORM
- Input validation with Pydantic
- Rate limiting on API endpoints
- Secure error handling

## 🤝 Contributing

1. Read `CLAUDE.md` for coding standards
2. Create feature branch
3. Write tests for new code
4. Run formatters and linters
5. Submit pull request

## 📄 License

[Your License Here]

## 🙏 Acknowledgments

Built with FastAPI, SQLAlchemy, Google Gemini, and the open-source community.
