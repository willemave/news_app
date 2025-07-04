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

# Build server command
SERVER_COMMAND="python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

# Add reload flag if in development
if [ "${ENVIRONMENT:-development}" = "development" ]; then
    SERVER_COMMAND="$SERVER_COMMAND --reload"
    echo "Running in development mode with auto-reload enabled"
fi

# Run the server (this will block until the server is stopped)
trap 'echo -e "\n\n✋ Server stopped by user"; exit 0' INT
eval $SERVER_COMMAND || {
    echo ""
    echo "❌ Server failed to start"
    exit 1
}