# Memory Bank Update Tasks

## Phase 1: Core Project Understanding
**Phase Goal:** Understand the fundamental architecture, technologies, and purpose of the news aggregation application.

**Tasks:**
- [x] Read main application entry point (app/main.py)
- [x] Read configuration file (app/config.py)
- [x] Read database models (app/models.py)
- [x] Read schemas (app/schemas.py)
- [x] Update ai-memory/README.md with core application structure

**Reference Files:**
- app/main.py
- app/config.py
- app/models.py
- app/schemas.py

## Phase 2: Scraping System Analysis
**Phase Goal:** Understand the scraping architecture and available scrapers.

**Tasks:**
- [x] Read scraping aggregator (app/scraping/aggregator.py)
- [x] Read news scraper (app/scraping/news_scraper.py)
- [x] Read RSS scraper (app/scraping/rss.py)
- [x] Read PDF scraper (app/scraping/pdf_scraper.py)
- [x] Read Raindrop integration (app/scraping/raindrop.py)
- [x] Read fallback scraper (app/scraping/fallback_scraper.py)
- [x] Update ai-memory/README.md with scraping system patterns

**Reference Files:**
- app/scraping/aggregator.py
- app/scraping/news_scraper.py
- app/scraping/rss.py
- app/scraping/pdf_scraper.py
- app/scraping/raindrop.py
- app/scraping/fallback_scraper.py

## Phase 3: Web Interface and API Analysis
**Phase Goal:** Understand the web interface, routing, and user-facing functionality.

**Tasks:**
- [ ] Read admin router (app/routers/admin.py)
- [ ] Read articles router (app/routers/articles.py)
- [ ] Read links router (app/routers/links.py)
- [ ] Read database layer (app/database.py)
- [ ] Read LLM integration (app/llm.py)
- [ ] Update ai-memory/README.md with web interface patterns

**Reference Files:**
- app/routers/admin.py
- app/routers/articles.py
- app/routers/links.py
- app/database.py
- app/llm.py

## Phase 4: Automation and Templates
**Phase Goal:** Understand the automation pipeline and frontend templates.

**Tasks:**
- [ ] Read cron pipeline (cron/run_full_pipeline.py)
- [ ] Read daily ingest (cron/daily_ingest.py)
- [ ] Read process articles (cron/process_articles.py)
- [ ] Examine key templates (templates/base.html, templates/admin_dashboard.html)
- [ ] Read static assets (static/css/styles.css, static/js/main.js)
- [ ] Update ai-memory/README.md with automation and frontend patterns

**Reference Files:**
- cron/run_full_pipeline.py
- cron/daily_ingest.py
- cron/process_articles.py
- templates/base.html
- templates/admin_dashboard.html
- static/css/styles.css
- static/js/main.js

## Phase 5: Project Configuration and Dependencies
**Phase Goal:** Understand project setup, dependencies, and deployment.

**Tasks:**
- [ ] Read project configuration (pyproject.toml)
- [ ] Read requirements (requirements.txt)
- [ ] Read startup script (start_server.sh)
- [ ] Read project README (README.md)
- [ ] Examine test structure (tests/)
- [ ] Update ai-memory/README.md with project setup and testing patterns
- [ ] Create ai-memory/PROMPT.md placeholder
- [ ] Final review and completion of ai-memory/README.md

**Reference Files:**
- pyproject.toml
- requirements.txt
- start_server.sh
- README.md
- tests/

**Key Learnings/Decisions from this Phase (to be filled at end of Phase):**
[To be completed during execution]

## New Dependencies:
[To be identified during exploration]
