#!/bin/bash
# Startup script that runs Alembic migrations before starting the FastAPI server.
# This ensures the database schema is up-to-date on every deployment.

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

# Check if alembic.ini exists
if [ ! -f "alembic.ini" ]; then
    echo "ERROR: alembic.ini not found. Please initialize Alembic first."
    exit 1
fi

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

# Run migrations
echo ""
echo "🔄 Running database migrations..."
if ! run_command "Alembic migrations" python -m alembic upgrade head; then
    echo ""
    echo "❌ Migration failed! Server will not start."
    exit 1
fi

echo ""
echo "✅ Migrations completed successfully!"

# Start the FastAPI server
echo ""
echo "🚀 Starting FastAPI server..."

# Build server command arguments
SERVER_ARGS=(python -m uvicorn app.main:app --host 0.0.0.0 --port 8000)

# Add reload flag if in development
if [ "${ENVIRONMENT:-development}" = "development" ]; then
    SERVER_ARGS+=(--reload)
    echo "Running in development mode with auto-reload enabled"
fi

# Replace shell with uvicorn so Supervisor can manage the process tree directly
exec "${SERVER_ARGS[@]}" || {
    echo ""
    echo "❌ Server failed to start"
    exit 1
}
