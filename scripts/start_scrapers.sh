#!/bin/bash
# Startup script for running content scrapers.
# This ensures the database is properly initialized before scraping.

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Change to project root
cd "$PROJECT_ROOT"
echo "Working directory: $(pwd)"

# Check if virtual environment exists
if [ ! -f ".venv/bin/python" ]; then
    echo "ERROR: Virtual environment not found. Please run 'uv venv' first."
    exit 1
fi

# Activate virtual environment
source .venv/bin/activate

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

# Check if we need to run migrations
echo ""
echo "🔄 Checking database migrations..."
if [ -f "alembic.ini" ]; then
    # Check if there are pending migrations
    if python -m alembic current 2>&1 | grep -q "head"; then
        echo "✅ Database is up to date"
    else
        echo "⚠️  Database may need migrations. Run './scripts/start_server.sh' first to apply migrations."
    fi
else
    echo "⚠️  Alembic not configured. Proceeding without migration check."
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