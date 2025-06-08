**News Aggregation & Summarization App — Concise Overview (bullet-only)**

---

**Purpose**

* Aggregate news from web sites, RSS, PDFs, Reddit, podcasts.
* Auto-scrape, filter with an LLM, generate short + detailed summaries, store, and display in a web UI.

**Problems Solved**

* One place to read across sources.
* Automated scraping and status-tracked processing.
* Fast scanning via AI summaries.
* Admin visibility into pipeline health.

**Core Architecture**

* **API & UI**: FastAPI (`main.py`) with `articles`, `admin`, `links`; Jinja2 templates; HTMX for dynamic actions.
* **Scraping & Processing**: `processor.py` handles HTML/PDF download and extraction (Trafilatura, PyPDF2). HackerNews and Reddit scrapers enqueue links.
* **LLM**: `llm.py` uses Google Gemini 2.5 Flash to filter relevance and create dual-level summaries + keywords.
* **Queue**: Huey (SQLite backend) in `queue.py`; retries on 429; utility to drain queue.
* **Data**: SQLite via SQLAlchemy (`models.py`, `database.py`). Tables: Articles (includes summaries), CronLogs.
* **Vector Search**: ChromaDB for semantic lookup.
* **Automation**: Cron scripts (`cron/daily_ingest.py`, `cron/process_articles.py`) run scheduled ingest and batch processing.

**Tech Stack**

* Python 3.13, FastAPI, SQLAlchemy, Pydantic, SQLite.
* requests, Trafilatura, PyPDF2, PRAW.
* google-genai, ChromaDB, Huey.
* CrewAI for experimental multi-agent scraping.

**Key Workflows**

* Daily ingest adds new links (`status=new`).
* Queue worker downloads content, filters with LLM, saves summaries (`status=processed` or `failed`).
* Manual or auto approval marks articles as `approved`.
* Web UI lists articles; detail view shows full content and summaries; admin dashboard displays CronLogs and trigger buttons.

**Repository Highlights**

* `app/`: main, config, models, schemas, processor, llm, queue, routers.
* `app/scraping/`: HackerNews and Reddit scrapers.
* `cron/`: scheduled ingest and processing jobs.
* `scripts/`: dev helpers (run scrapers, CrewAI demo, migrations).
* `templates/` & `static/`: minimalist Bootstrap-style frontend.

**Configuration**

* `.env` controls Raindrop token (legacy), Google API key, Reddit creds, database paths, etc.
* Default local DB paths: `./news_app.db` (SQLite) and `./db/chroma.sqlite3` (ChromaDB).

This bullet list captures purpose, components, workflows, and tech choices without tables or extra detail.


This is a new app. The goal of this app is to scrape top news sites, rss feeds and pod casts. 

Technologies
1. Python
2. Pydantic for all models
3. SQLite for local sql database
4. HTMX for simple html rendering. 

Structure
1. app/scraping/ -- this is the main place to implement new scrapers. 
2. app/routers/ -- these are the routes for the web app
3. app/cron/ -- this includes all the crontabes. 
