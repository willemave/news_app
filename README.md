# Newsly

AI-powered news aggregation and summarization with a FastAPI backend and a native SwiftUI iOS app.

## What it does
- Ingests content from scrapers and user submissions
- Analyzes URLs, processes content, summarizes with LLMs, and generates images
- Serves a JSON API for the iOS app and Jinja admin UI

## Key docs
- `docs/architecture.md` — full system, schema, and API details
- `CLAUDE.md` — coding rules and workflow

## Quick start
```bash
uv sync
. .venv/bin/activate
alembic upgrade head
npx @tailwindcss/cli -i ./static/css/styles.css -o ./static/css/app.css
scripts/start_server.sh
scripts/start_workers.sh
scripts/start_scrapers.sh
```

## Common commands
```bash
pytest app/tests/ -v
ruff check .
ruff format .
```

## Configuration
- Copy `.env.example` → `.env`
- Required:
  - `DATABASE_URL`
  - `JWT_SECRET_KEY`
  - `ADMIN_PASSWORD`
- Optional keys: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `EXA_API_KEY`

## Repo map (high level)
- `app/` FastAPI backend
- `client/newsly/` SwiftUI iOS app + ShareExtension
- `scripts/` workers/scrapers
- `docs/` architecture and plans

## API entry points
- `GET /api/content` (list)
- `GET /api/content/{id}` (detail)
- `POST /api/content/submit` (user submissions)
- `POST /api/chat/...` (chat sessions + messages)
