#!/bin/bash
# Startup script for running content scrapers.
# This ensures the database is properly initialized before scraping.

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Change to project root
cd "$PROJECT_ROOT"
echo "Working directory: $(pwd)"

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "ERROR: .env file not found at $PROJECT_ROOT/.env"
    echo ""
    echo "Please ensure:"
    echo "1. .env file exists in the project root: $PROJECT_ROOT/"
    echo "2. Copy from .env.example if needed: cp .env.example .env"
    echo "3. Configure DATABASE_URL and other required variables"
    exit 1
fi

# If there is a project venv, use it, otherwise assume the current env is correct
if [ -f ".venv/bin/activate" ]; then
    echo "Activating project .venv"
    # shellcheck source=/dev/null
    source .venv/bin/activate
else
    echo "No .venv found, using current Python environment: $(python -c 'import sys; print(sys.executable)')"
fi

# Display database target for transparency
DATABASE_TARGET=$(PROJECT_ROOT="$PROJECT_ROOT" python <<'PY'
import os
from pathlib import Path
from sqlalchemy.engine.url import make_url
from app.core.settings import get_settings

project_root = Path(os.environ["PROJECT_ROOT"]).resolve()
settings = get_settings()
url = str(settings.database_url)
parsed = make_url(url)

if parsed.drivername.startswith("sqlite"):
    database = parsed.database or ""
    db_path = Path(database).expanduser()
    if not db_path.is_absolute():
        db_path = (project_root / db_path).resolve()
    else:
        db_path = db_path.resolve()
    print(db_path)
else:
    print(url)
PY
)
echo "Database target: ${DATABASE_TARGET}"

# Function to run commands with nice output
run_command() {
    local description="$1"
    shift
    echo ""
    echo "============================================================"
    echo "Running: $description"
    echo "Command: $*"
    echo "============================================================"
    
    if "$@"; then
        return 0
    else
        echo "ERROR: $description failed!"
        return 1
    fi
}

# Parse command line arguments
SCRAPERS=""
DEBUG_FLAG=""
STATS_FLAG=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --debug)
            DEBUG_FLAG="--debug"
            shift
            ;;
        --show-stats)
            STATS_FLAG="--show-stats"
            shift
            ;;
        --scrapers)
            shift
            SCRAPERS="--scrapers"
            # Collect all scraper names until next flag or end
            while [[ $# -gt 0 && ! "$1" =~ ^-- ]]; do
                SCRAPERS="$SCRAPERS $1"
                shift
            done
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--debug] [--show-stats] [--scrapers scraper1 scraper2 ...]"
            exit 1
            ;;
    esac
done

# Check database connection
echo ""
echo "🔍 Checking database connection..."
if ! python -c "from app.core.db import init_db; init_db()" 2>/dev/null; then
    echo "❌ Database connection failed!"
    echo ""
    echo "Please ensure:"
    echo "1. Database is running"
    echo "2. DATABASE_URL is correctly set in .env"
    echo "3. Database exists and is accessible"
    exit 1
fi
echo "✅ Database connection successful!"

# Run migrations (idempotent - safe to run multiple times)
echo ""
echo "🔄 Running database migrations..."
if [ -f "alembic.ini" ]; then
    if ! run_command "Alembic migrations" python -m alembic upgrade head; then
        echo ""
        echo "⚠️  Migration failed! Continuing anyway, but may encounter errors."
        echo "    Check that DATABASE_URL is correct and database is accessible."
    else
        echo "✅ Migrations completed successfully!"
    fi
else
    echo "⚠️  Alembic not configured. Skipping migrations."
fi

# Build scraper command
SCRAPER_COMMAND="python scripts/run_scrapers.py $DEBUG_FLAG $STATS_FLAG $SCRAPERS"

# Show what we're about to run
echo ""
echo "🚀 Starting content scrapers..."
if [ -n "$SCRAPERS" ]; then
    echo "Running specific scrapers: ${SCRAPERS#--scrapers }"
else
    echo "Running all available scrapers"
fi

if [ -n "$DEBUG_FLAG" ]; then
    echo "Debug mode: ENABLED"
fi

if [ -n "$STATS_FLAG" ]; then
    echo "Statistics: ENABLED"
fi

# Run the scrapers
trap 'echo -e "\n\n✋ Scrapers stopped by user"; exit 0' INT
echo ""
eval $SCRAPER_COMMAND || {
    echo ""
    echo "❌ Scrapers failed to complete"
    exit 1
}

echo ""
echo "✅ Scraping completed successfully!"
echo ""
echo "💡 To process the scraped content, run: ./scripts/start_workers.sh"
