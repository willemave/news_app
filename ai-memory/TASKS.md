# News App Development Tasks

## Phase 0: Podcast Feature Implementation 🎙️

### Backend Development

#### 1. Database Schema Updates
- [ ] Create migration script to add Podcasts table
  - [ ] Fields: id, title, url, file_path, transcribed_text_path, short_summary, detailed_summary, publication_date, download_date, podcast_feed_name, status
  - [ ] Add PodcastStatus enum (new, downloaded, transcribed, summarized, failed)
  - [ ] Create indexes on url and status fields
- [ ] Update ai-memory/README.md with new database schema

#### 2. Podcast RSS Scraper
- [ ] Create `app/scraping/podcast_rss_scraper.py`
  - [ ] Copy patterns from `app/scraping/substack_scraper.py`
  - [ ] Load podcast feeds from YAML configuration
  - [ ] Parse RSS feeds using feedparser
  - [ ] Extract podcast metadata (title, url, publication date, enclosure URL)
  - [ ] Create Podcast records with status='new'
- [ ] Create `config/podcasts.yml` for podcast RSS feed URLs
- [ ] Add tests in `tests/scraping/test_podcast_rss_scraper.py`

#### 3. Podcast Downloader Class  
- [ ] Create `app/processing/podcast_downloader.py`
  - [ ] Use RobustHttpClient for downloading audio files
  - [ ] Implement download with progress tracking
  - [ ] Save to organized folder structure: `data/podcasts/{feed_name}/{sanitized_title}.{ext}`
  - [ ] Handle various audio formats (mp3, m4a, etc.)
  - [ ] Update Podcast record with file_path and status='downloaded'
- [ ] Add queue task `download_podcast_task()` in `app/queue.py`
- [ ] Write tests in `tests/processing/test_podcast_downloader.py`

#### 4. Podcast Audio-to-Text Converter
- [ ] Create `app/processing/podcast_converter.py`
  - [ ] Implement WhisperConverter class using whisper v3 turbo
  - [ ] Add method to convert audio to text: `convert_to_text(audio_path) -> text_path`
  - [ ] Save transcription as `.txt` file alongside audio
  - [ ] Update Podcast record with transcribed_text_path and status='transcribed'
- [ ] Add queue task `transcribe_podcast_task()` in `app/queue.py`
- [ ] Handle errors gracefully (missing files, conversion failures)
- [ ] Write tests in `tests/processing/test_podcast_converter.py`

#### 5. Podcast Summarization
- [ ] Extend `app/llm.py` with `summarize_podcast_transcript()` function
  - [ ] Adapt existing summarize_article logic for podcast transcripts
  - [ ] Consider longer context windows for podcast content
- [ ] Add queue task `summarize_podcast_task()` in `app/queue.py`
  - [ ] Read transcript from file
  - [ ] Generate short and detailed summaries
  - [ ] Update Podcast record with summaries and status='summarized'

#### 6. Podcast Processing Pipeline
- [ ] Create `app/processing/podcast_processor.py`
  - [ ] Orchestrate the full pipeline: download → transcribe → summarize
  - [ ] Handle state transitions and error recovery
  - [ ] Integrate with existing queue system
- [ ] Add `process_new_podcasts()` function to process all new podcasts

#### 7. API Router for Podcasts
- [ ] Create `app/routers/podcasts.py`
  - [ ] GET `/podcasts` - List all podcasts with pagination
  - [ ] GET `/podcasts/{id}` - Get podcast details including transcript and summaries
  - [ ] Add filtering by status, date range, feed name
- [ ] Register router in `app/main.py`
- [ ] Create Pydantic schemas in `app/schemas.py` for PodcastResponse

#### 8. Testing Script
- [ ] Create `scripts/test_podcast_pipeline.py`
  - [ ] Test RSS scraping
  - [ ] Test podcast downloading  
  - [ ] Test audio-to-text conversion
  - [ ] Test summarization
  - [ ] Verify complete pipeline flow

### Frontend Development

#### 1. Navigation Update
- [ ] Update `templates/base.html` to add "Podcasts" link in navigation
- [ ] Ensure consistent styling with existing navigation

#### 2. Podcast List Page
- [ ] Create `templates/podcasts.html`
  - [ ] Display podcast titles, feed names, publication dates
  - [ ] Add status indicators (downloaded, transcribed, summarized)
  - [ ] Implement pagination
  - [ ] Add search/filter functionality
  - [ ] Make titles clickable to view details

#### 3. Podcast Detail Page
- [ ] Create `templates/podcast_detail.html`
  - [ ] Show podcast metadata (title, feed, date, etc.)
  - [ ] Display short summary prominently
  - [ ] Show detailed summary in expandable section
  - [ ] Add transcript viewer with collapsible sections
  - [ ] Include download link for audio file
  - [ ] Add back navigation to podcast list

#### 4. Styling and JavaScript
- [ ] Update `static/css/styles.css` with podcast-specific styles
  - [ ] Status badges for podcast processing states
  - [ ] Transcript viewer styling
  - [ ] Audio player integration (if needed)
- [ ] Run TailwindCSS build: `npx @tailwindcss/cli -i ./static/css/styles.css -o ./static/css/app.css`
- [ ] Update `static/js/main.js` if needed for interactive elements

### Configuration and Documentation

#### 1. Dependencies
- [ ] Add openai-whisper to `pyproject.toml`
- [ ] Run `uv add openai-whisper`
- [ ] Update requirements.txt if needed

#### 2. Configuration Files
- [ ] Create `config/podcasts.yml` with initial podcast feeds
  ```yaml
  feeds:
    - name: "Example Tech Podcast"
      url: "https://example.com/podcast/rss"
    - name: "AI News Podcast" 
      url: "https://ainews.example.com/rss"
  ```

#### 3. Update Memory Bank
- [ ] Update `ai-memory/README.md` with:
  - [ ] New podcast architecture section
  - [ ] Podcast processing workflow
  - [ ] New database models
  - [ ] API endpoints documentation
- [ ] Mark completed tasks in this file

### Deployment and Testing

#### 1. Integration Testing
- [ ] Test complete podcast pipeline end-to-end
- [ ] Verify queue processing for podcasts
- [ ] Test error handling and recovery
- [ ] Ensure no conflicts with existing article processing

#### 2. Performance Testing
- [ ] Test with large audio files
- [ ] Monitor memory usage during transcription
- [ ] Verify concurrent processing works correctly

#### 3. Documentation
- [ ] Add usage instructions to README
- [ ] Document podcast feed configuration
- [ ] Create troubleshooting guide for common issues

---

## Phase 1: Core System Improvements

### Database & Migration Tasks
- [ ] **Review Migration Scripts**: Audit existing migration scripts in `scripts/migrations/`
  - [ ] Read `scripts/migrations/add_local_path_to_articles.py`
  - [ ] Read `scripts/migrations/add_status_to_articles.py`
  - [ ] Read `scripts/migrations/add_skipped_status.py`
  - [ ] Read `scripts/migrations/add_skip_reason_to_failure_logs.py`
- [ ] **Update ai-memory/README.md** with migration patterns and database evolution

### Configuration Management
- [ ] **Review Configuration Files**: Analyze current config setup
  - [ ] Read `app/config.py` for settings management
  - [ ] Read `app/database.py` for database configuration
  - [ ] Verify environment variable usage patterns
- [ ] **Update ai-memory/README.md** with configuration patterns

## Phase 2: Processing Pipeline Enhancement

### Strategy Pattern Refinement
- [ ] **Review Base Strategy**: Analyze abstract base class implementation
  - [ ] Read `app/processing_strategies/base_strategy.py`
  - [ ] Document strategy interface and contracts
- [ ] **Strategy Testing**: Review and enhance strategy tests
  - [ ] Read `tests/processing_strategies/test_html_strategy.py`
  - [ ] Read `tests/processing_strategies/test_pdf_strategy.py`
  - [ ] Read `tests/processing_strategies/test_pubmed_strategy.py`
  - [ ] Read `tests/processing_strategies/test_url_processor_factory.py`
- [ ] **Update ai-memory/README.md** with strategy pattern details

### Content Processing Optimization
- [ ] **Local Article Processing**: Review and enhance local content handling
  - [ ] Read `scripts/process_local_articles.py` implementation
  - [ ] Test local file processing workflow
  - [ ] Document local vs remote processing patterns
- [ ] **Update ai-memory/README.md** with content processing workflows

## Phase 3: Web Interface & API Enhancement

### Router Analysis
- [ ] **Review API Endpoints**: Analyze current web interface
  - [ ] Read `app/routers/articles.py` for article endpoints
  - [ ] Read `app/routers/admin.py` for admin functionality
  - [ ] Document API patterns and response formats
- [ ] **Template System**: Review frontend implementation
  - [ ] Read key templates: `templates/base.html`, `templates/articles.html`
  - [ ] Read `templates/admin_dashboard.html`, `templates/detailed_article.html`
  - [ ] Document template patterns and HTMX usage
- [ ] **Update ai-memory/README.md** with web interface architecture

### Static Assets & Styling
- [ ] **Frontend Assets**: Review styling and JavaScript
  - [ ] Read `static/css/styles.css` and `static/js/main.js`
  - [ ] Document TailwindCSS build process
  - [ ] Review responsive design patterns
- [ ] **Update ai-memory/README.md** with frontend build process

## Phase 4: Testing & Quality Assurance

### Test Coverage Analysis
- [ ] **Core Testing**: Review main application tests
  - [ ] Read `tests/conftest.py` for test configuration
  - [ ] Read `tests/test_content_download.py`
  - [ ] Read `tests/test_duplicate_url_skipping.py`
  - [ ] Read `tests/test_local_article_processor.py`
- [ ] **HTTP Client Testing**: Review network layer tests
  - [ ] Read `tests/http_client/test_robust_http_client.py`
  - [ ] Document testing patterns for async HTTP operations
- [ ] **Update ai-memory/README.md** with testing strategies

### Integration Testing
- [ ] **End-to-End Tests**: Review integration test patterns
  - [ ] Read `tests/test_llm_json_parsing_error.py`
  - [ ] Read `tests/test_skip_reason.py`
  - [ ] Read `tests/test_fixes_simple.py`
- [ ] **Scraper Testing**: Review scraper test implementations
  - [ ] Read `tests/scraping/test_substack_scraper.py`
  - [ ] Document scraper testing patterns
- [ ] **Update ai-memory/README.md** with integration testing approach

## Phase 5: Automation & Deployment

### Cron Job Analysis
- [ ] **Scheduled Tasks**: Review automation implementation
  - [ ] Read `cron/run_scrapers_job.py` for scheduled execution
  - [ ] Document cron job patterns and scheduling
  - [ ] Review error handling in automated tasks
- [ ] **Update ai-memory/README.md** with automation architecture

### Utility Scripts
- [ ] **Development Tools**: Review utility scripts
  - [ ] Read `scripts/run_scrapers.py` for manual execution
  - [ ] Read `scripts/clear_database.py` for database management
  - [ ] Read `scripts/db_quick_view.py` and `scripts/display_database.py`
- [ ] **Update ai-memory/README.md** with development workflow tools

## Phase 6: Documentation & Knowledge Management

### Code Documentation
- [ ] **API Documentation**: Generate and review API docs
  - [ ] Document FastAPI endpoint schemas
  - [ ] Create OpenAPI documentation
  - [ ] Document Pydantic model schemas
- [ ] **Update ai-memory/README.md** with API documentation patterns

### Architecture Documentation
- [ ] **System Design**: Document architectural decisions
  - [ ] Create sequence diagrams for processing pipeline
  - [ ] Document data flow and state transitions
  - [ ] Create deployment and scaling considerations
- [ ] **Update ai-memory/README.md** with architectural decisions

## Ongoing Maintenance Tasks

### Regular Updates
- [ ] **Dependency Management**: Keep dependencies current
  - [ ] Review `pyproject.toml` for outdated packages
  - [ ] Test compatibility with new versions
  - [ ] Update security-related dependencies
- [ ] **Performance Monitoring**: Track system performance
  - [ ] Monitor queue processing times
  - [ ] Track LLM API usage and costs
  - [ ] Monitor database growth and performance

### Code Quality
- [ ] **Linting & Formatting**: Maintain code quality
  - [ ] Run `ruff check` and `ruff format` regularly
  - [ ] Ensure type hints are comprehensive
  - [ ] Maintain test coverage above 80%
- [ ] **Security Review**: Regular security audits
  - [ ] Review environment variable usage
  - [ ] Audit external API integrations
  - [ ] Check for SQL injection vulnerabilities

## Key Files to Monitor

### Critical Application Files
- `app/main.py` - Application entry point
- `app/processor.py` - Core processing logic
- `app/models.py` - Database schema
- `app/llm.py` - LLM integration
- `app/queue.py` - Background processing

### Configuration Files
- `pyproject.toml` - Dependencies and project config
- `config/substack.yml` - Scraper configuration
- `.env` - Environment variables (not in repo)

### Key Test Files
- `tests/conftest.py` - Test configuration
- `tests/processing_strategies/` - Strategy tests
- `tests/http_client/` - Network layer tests

## Learning Notes

### Architecture Patterns
- **Strategy Pattern**: Successfully implemented for URL processing with clean factory registration
- **Async Processing**: Comprehensive async/await usage with proper resource management
- **Error Handling**: Multi-layered error handling with specific failure logging
- **Queue Management**: Huey integration with retry logic for rate-limited APIs

### Development Workflow
- **Testing**: Pytest with async support and comprehensive mocking
- **Dependencies**: UV package management with development groups
- **Code Quality**: Ruff for linting and formatting
- **Database**: SQLAlchemy with enum-based status tracking
