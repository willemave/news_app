# News Aggregation & Summarization Platform

A FastAPI-based intelligent news aggregation platform that automatically collects, processes, and summarizes content from multiple sources including web articles, RSS feeds, Reddit, and podcasts. The system uses LLM technology to provide intelligent summarization and content classification.

## Key Features

- **Multi-Source Content Aggregation**: Scrapes content from HackerNews, Reddit, Substack RSS feeds, and podcast RSS feeds
- **Intelligent Processing**: Uses Google Gemini 2.5 Flash Lite for content summarization and classification
- **Unified Content Model**: Single architecture handles both articles and podcasts seamlessly
- **Strategy Pattern Processing**: Pluggable strategies for different content types (HTML, PDF, images, ArXiv papers)
- **Read Status Tracking**: Track which content has been read (single-user app)
- **Admin Dashboard**: Monitor pipeline status, view logs, manage content processing
- **HTMX-Enabled UI**: Dynamic, responsive web interface with markdown rendering
- **Database-Backed Queue**: Reliable task processing with retry logic
- **Comprehensive Error Handling**: Structured logging with full context preservation

## Architecture Overview

The application follows a clean architecture pattern with clear separation of concerns:

- **Scrapers** collect content URLs and metadata from various sources
- **Processing Pipeline** downloads and extracts content using appropriate strategies
- **LLM Service** generates structured summaries with classification (TO_READ/SKIP)
- **Web Interface** presents content with filtering, search, and admin controls
- **Task Queue** manages background processing with sequential execution

## Technology Stack

### Backend
- **Python 3.13** with type hints
- **FastAPI** - Modern async web framework
- **SQLAlchemy 2.0** - ORM with async support
- **Pydantic v2** - Data validation and settings management
- **SQLite/PostgreSQL** - Database (configurable)

### Content Processing
- **crawl4ai** - Advanced web scraping
- **trafilatura** - Web article extraction
- **PyPDF2** - PDF processing
- **faster-whisper** - Podcast transcription
- **feedparser** - RSS feed parsing
- **beautifulsoup4** - HTML parsing

### LLM Integration
- **Google Gemini 2.5 Flash Lite** - Primary summarization model
- **OpenAI API** (optional) - Alternative transcription service
- Structured output with Pydantic schemas

### Frontend
- **Jinja2** - Template engine with markdown support
- **TailwindCSS** - Utility-first CSS framework
- **HTMX** - Dynamic UI without JavaScript frameworks
- **Python-Markdown** - Rich text rendering with extensions

### Development Tools
- **uv** - Fast Python package manager
- **ruff** - Python linter and formatter
- **pytest** - Testing framework with async support
- **alembic** - Database migrations

## Installation & Setup

### Prerequisites
- Python 3.13+
- Node.js (for TailwindCSS)
- SQLite (default) or PostgreSQL

### Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd news_app
   ```

2. **Create virtual environment with uv**
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   uv sync
   npm install  # For TailwindCSS
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration:
   # - GOOGLE_API_KEY (required for LLM)
   # - DATABASE_URL (optional, defaults to SQLite)
   # - Other optional settings
   ```

5. **Initialize database**
   ```bash
   alembic upgrade head
   ```

6. **Build CSS**
   ```bash
   npx @tailwindcss/cli -i ./static/css/styles.css -o ./static/css/app.css
   ```

7. **Run the application**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
   ```

## Usage

### Running Scrapers

Collect content from all configured sources:
```bash
python scripts/run_scrapers.py
```

Run specific scrapers:
```bash
python scripts/run_scrapers.py --scrapers hackernews reddit
```

### Processing Content

Start the processing pipeline workers:
```bash
python scripts/start_workers.sh
# Or for manual control:
python scripts/run_workers.py --max-workers 2
```

### Web Interface

Access the application at `http://localhost:8001`

- **Home** (`/`) - View all content with filtering
- **Articles** (`/articles`) - Article-specific view  
- **Podcasts** (`/podcasts`) - Podcast-specific view
- **Admin** (`/admin`) - Pipeline monitoring and controls
- **API** (`/api/content`) - RESTful API endpoints

### Utility Scripts

- `scripts/run_scrapers.py` - Run content scrapers
- `scripts/start_workers.sh` - Start processing workers
- `scripts/start_scrapers.sh` - Start scraper daemon
- `scripts/run_pending_tasks.py` - Process specific pending tasks
- `scripts/reset_content_processing.py` - Reset content status
- `scripts/analyze_logs_for_fixes.py` - Analyze error logs
- `scripts/resummarize_podcasts.py` - Re-run podcast summarization
- `scripts/retranscribe_podcasts.py` - Re-run podcast transcription

## Configuration

### Feed Configuration

Configure content sources in YAML files:

- `config/substack.yml` - Substack RSS feeds
- `config/podcasts.yml` - Podcast RSS feeds  
- `config/reddit.yml` - Reddit subreddits

Example Substack configuration:
```yaml
feeds:
  - url: https://example.substack.com/feed
    source_name: Example Newsletter
```

### Application Settings

Key settings in `.env`:
```bash
# LLM Configuration
GOOGLE_API_KEY=your-api-key
GEMINI_MODEL=gemini-2.5-flash-lite

# Database
DATABASE_URL=sqlite:///./news_app.db

# Processing
MAX_WORKERS=4
TASK_PROCESSING_INTERVAL=5

# Content Limits
MAX_CONTENT_LENGTH=500000
SUMMARY_MAX_WORDS=500
```

## Development

### Project Structure
```
news_app/
├── app/                    # Main application code
│   ├── core/              # Core functionality (DB, settings, logging)
│   ├── models/            # SQLAlchemy models and schemas
│   ├── routers/           # API endpoints
│   ├── services/          # Business logic layer
│   ├── pipeline/          # Content processing pipeline
│   ├── processing_strategies/  # Content type handlers
│   ├── scraping/          # Content scrapers
│   └── templates/         # Jinja2 templates
├── scripts/               # Utility scripts
├── config/               # Feed configurations
├── tests/                # Test suite
├── alembic/              # Database migrations
├── ai-memory/            # AI agent context
└── static/               # CSS and JavaScript
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_read_status.py -v
```

### Code Quality

```bash
# Format code
ruff format

# Lint code  
ruff check

# Type checking
mypy app
```

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## API Documentation

Interactive API documentation is available at:
- Swagger UI: `http://localhost:8001/docs`
- ReDoc: `http://localhost:8001/redoc`

Key endpoints:
- `GET /api/content` - List content with filtering
- `GET /api/content/{id}` - Get specific content
- `POST /api/content/{id}/read` - Mark content as read
- `GET /api/content/stats` - Content statistics

## Contributing

1. Follow the coding standards in `CLAUDE.md`
2. Write tests for new functionality
3. Run formatters and linters before committing
4. Update `ai-memory/README.md` for architectural changes
5. Use conventional commit messages

## License

[Specify your license here]

## Acknowledgments

Built with FastAPI, SQLAlchemy, and the Google Gemini API.