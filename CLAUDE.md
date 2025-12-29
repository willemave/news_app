# Newsly Development Guide

> For comprehensive technical documentation (database schema, API endpoints, Pydantic schemas, project structure), see **[docs/architecture.md](docs/architecture.md)**.

---

## 1. Python / FastAPI Coding Rules

* **Functions over classes**.
* **Full type hints**; validate with **Pydantic v2** models. Use `typing` for complex types.
* **RORO** pattern (receive object, return object).
* `lower_snake_case` for files/dirs; verbs in variables (`is_valid`, `has_permission`).
* Guard-clause error handling; early returns over nested `else`.
* **Docstrings**: Use Google-style for all public functions/classes.
* **Constants**: Define in `app/constants.py` or module-level UPPER_CASE.

---

## 2. FastAPI Best Practices

* Use **lifespan** context, not `startup/shutdown` events.
* Inject DB/session with dependencies; use `Annotated` for cleaner signatures.
* Middleware order matters: logging → tracing → CORS → error capture.

---

## 3. Code Quality & Safety

* **No hardcoded secrets**; use `pydantic-settings` for config management.
* **Input validation**: Always validate at boundaries (API, external services).
* **SQL injection prevention**: Use parameterized queries, never f-strings.
* **Graceful degradation**: Circuit breakers for external services.
* **Error logging**: Use `logger.error()` or `logger.exception()` directly with structured `extra` fields (see below).

### Error Logging Convention

Use `logger.error()` or `logger.exception()` directly with structured `extra` fields:

```python
from app.core.logging import get_logger
logger = get_logger(__name__)

# For errors with tracebacks (in except blocks):
try:
    process_item(item_id)
except Exception as e:
    logger.exception(
        "Failed to process item %s: %s",
        item_id,
        e,
        extra={
            "component": "worker_name",
            "operation": "process_item",
            "item_id": item_id,
            "context_data": {"url": url, "status": status},
        },
    )

# For error conditions without tracebacks:
logger.error(
    "Invalid state for item %s",
    item_id,
    extra={
        "component": "validator",
        "operation": "validate",
        "context_data": {"expected": "active", "actual": state},
    },
)
```

Standard `extra` fields:
- `component`: Module/worker name (e.g., `"content_worker"`, `"http_service"`)
- `operation`: Operation name (e.g., `"summarize"`, `"http_fetch"`)
- `item_id`: ID of item being processed (optional)
- `context_data`: Dict with additional context (optional)

Errors at level ERROR+ are automatically written to JSONL files in `logs/errors/`.

---

## 4. Testing Requirements

* **Write tests for all new functionality** in `app/tests/` using idiomatic pytest.
* Test structure mirrors app structure: `tests/routers/`, `tests/services/`, etc.
* Test file naming: `test_<module_name>.py`.
* **Test categories**:
  - Unit tests: isolated function/class testing
  - Integration tests: API endpoints with test DB
  - Contract tests: external service interactions
* Use pytest fixtures for setup/teardown.
* **TestClient** from FastAPI for endpoint testing.
* Mock external dependencies with `pytest-mock` or `unittest.mock`.
* **Run tests**: `pytest app/tests/ -v`
* **Test data**: Use factories or fixtures, never production data.

---

## 5. Development Workflow

* **Pre-commit hooks**: `ruff` for linting/formatting
* **Environment management**: `.env.example` template; never commit `.env`. Use `app/core/settings.py` and Pydantic for settings.
* **Database migrations**: Alembic with descriptive revision messages.
* **UI**: Jinja2 templates for HTML pages (not a JavaScript/React app).
* **Error responses**: Consistent format with error codes, messages, details.
* **Tailwind CSS**: Write to `./static/css/styles.css`, build with:
  ```bash
  npx @tailwindcss/cli -i ./static/css/styles.css -o ./static/css/app.css
  ```

### Pipeline Notes
* `POST /api/content/submit` creates `content_type=unknown`, queues `ANALYZE_URL` → `PROCESS_CONTENT`.
* `ANALYZE_URL` uses pattern matching + LLM page analysis to set content type/platform/media.
* `SUMMARIZE` writes interleaved summaries for articles/podcasts, news digests for news, then enqueues `GENERATE_IMAGE`.
* `GENERATE_IMAGE` creates thumbnails/infographics and exposes `image_url`/`thumbnail_url` in API responses.

---

## 6. Beads Workflow (Issue Tracking)

Track work using beads (`.beads/` directory). TodoWrite tool is fine for in-session task tracking.

### LLM Task Planning Workflow
1. **Start session**: Run `bd ready` to see available work
2. **Plan complex tasks**: After planning, **always** use `bd create` to break work into beads issues with dependencies. This is required for any multi-step implementation.
3. **Claim work**: `bd update <id> --status=in_progress` before starting each task
4. **Complete work**: `bd close <id>` immediately when done
5. **Iterate**: Check `bd ready` for next available task

### Essential Commands
```bash
bd ready                              # Show issues ready to work (no blockers)
bd list --status=open                 # All open issues
bd list --status=in_progress          # Active work
bd show <id>                          # Detailed issue view
bd create --title="..." --type=task   # New issue (task|bug|feature)
bd update <id> --status=in_progress   # Claim work
bd close <id>                         # Mark complete
bd sync                               # Sync with git remote
```

### Dependencies (for multi-step plans)
```bash
bd dep <from> <to>                    # Add blocker (from blocks to)
bd blocked                            # Show blocked issues
```

Example: Create dependent tasks for a feature:
```bash
bd create --title="Design API schema" --type=task        # → beads-001
bd create --title="Implement endpoints" --type=task      # → beads-002
bd create --title="Write tests" --type=task              # → beads-003
bd dep beads-001 beads-002            # Schema blocks implementation
bd dep beads-002 beads-003            # Implementation blocks tests
```

### Session Close Protocol
Before completing work, **always run**:
```bash
ruff check . && ruff format .         # Lint and format Python changes
git status                            # Check changes
git diff                              # Review all changes before committing
git add <files>                       # Stage code
bd sync                               # Commit beads
git commit -m "..."                   # Commit code
bd sync                               # Sync any new beads
```

**Important**: After closing beads tasks and before committing, always show `git diff` of all changed files to the user for review. This ensures visibility into what was implemented.

Only push if explicitly requested by the user.

---

## 7. Package & Dev Tools

### Package Management (uv)
```bash
uv sync                    # Install all dependencies
uv add <package>           # Add dependency
uv add --dev <package>     # Add dev dependency
source .venv/bin/activate  # Activate venv
```

### Database
```bash
alembic upgrade head       # Apply migrations
alembic revision -m "..."  # Create migration
```

### Code Quality
```bash
ruff check .               # Lint
ruff format .              # Format
pytest app/tests/ -v       # Run tests
```

### Running the App
```bash
# Local development
uv sync && . .venv/bin/activate
alembic upgrade head
scripts/start_server.sh              # API server
scripts/start_workers.sh             # Task workers
scripts/start_scrapers.sh            # Content scrapers

# Docker
docker compose up -d                 # Start all services
docker compose up -d --build         # Rebuild and start
```

---

## 8. Preferred Dev Tools

* **LLM internet search**: Use the EXA MCP `web_search_exa` tool for any web/internet lookups (and `get_code_context_exa` for external API/library docs).
* **LLM code search**: Use the Morph MCP `warp_grep` tool for repository code searches before opening files.

| Tool | Purpose | Example |
|------|---------|---------|
| **fd** | Fast file finder | `fd -e py foo` |
| **rg** | Fast code search | `rg "TODO"` |
| **ast-grep (sg)** | AST-aware search | `sg -p 'if ($A) { $B }'` |
| **jq** | JSON processor | `cat data.json \| jq '.items'` |
| **fzf** | Fuzzy finder | `history \| fzf` |
| **bat** | Better cat | `bat file.py` |
| **eza** | Modern ls | `eza -l --git` |
| **httpie** | HTTP client | `http GET api/foo` |
| **delta** | Better git diff | `git diff` (with config) |

---

## 9. Quick Reference

### Key Entry Points
| File | Purpose |
|------|---------|
| `app/main.py` | FastAPI app entry |
| `app/core/settings.py` | Configuration |
| `app/core/db.py` | Database setup |
| `app/models/schema.py` | ORM models |
| `app/services/content_analyzer.py` | URL analysis (LLM + trafilatura) |
| `app/services/feed_detection.py` | RSS/Atom feed detection + classification |
| `app/services/image_generation.py` | AI image + thumbnail generation |
| `scripts/run_workers.py` | Worker entry |
| `scripts/run_scrapers.py` | Scraper entry |
| `client/newsly/ShareExtension/ShareViewController.swift` | iOS share extension entry |

### Environment Variables (Required)
```bash
DATABASE_URL="sqlite:///./news_app.db"
JWT_SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_urlsafe(32))">
ADMIN_PASSWORD=<secure-password>
```

### Content Metadata + API Fields
* `summary_type=interleaved` for article/podcast summaries.
* User submissions may include `detected_feed` metadata (RSS/Atom classification).
* `image_url` + `thumbnail_url` are returned in content list/detail when available.

### Content Types
- `article` - Web articles, blog posts, papers
- `podcast` - Audio/video episodes
- `news` - Aggregated news items (HN, Techmeme)

### Status Lifecycle
```
new → pending → processing → completed
                    ↓
                  failed → (retry) → processing
                    ↓
                 skipped
```

---

## 10. Security Warnings (MVP)

- **Apple token verification DISABLED** — Must implement before production (see `app/core/security.py:106`)
- **Admin sessions IN-MEMORY** — Must migrate to Redis/DB for production (see `app/routers/auth.py:31`)

---

**Keep all replies short, technical, and complete.**

**Always run `ruff check` on touched Python files (or the repo) after a set of changes, and fix violations before final handoff whenever possible.**

For detailed documentation on:
- Complete project structure
- Database schema
- API endpoints
- Pydantic schemas
- Operational scripts
- iOS client architecture
- Authentication system

See **[docs/architecture.md](docs/architecture.md)**.
