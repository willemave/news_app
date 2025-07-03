#!/bin/bash
# Wait for database migrations to complete before starting worker

echo "🔄 Waiting for database migrations to complete..."

# Maximum wait time (5 minutes)
MAX_WAIT=300
WAIT_TIME=0
SLEEP_INTERVAL=5

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Change to project root
cd "$PROJECT_ROOT"

# Activate virtual environment
source .venv/bin/activate

# Wait for the health check to be available
while [ $WAIT_TIME -lt $MAX_WAIT ]; do
    # Try to connect to the health endpoint
    if curl -s -f http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ Health check passed! Starting worker..."
        break
    fi
    
    echo "⏳ Waiting for server to be ready... ($WAIT_TIME/$MAX_WAIT seconds)"
    sleep $SLEEP_INTERVAL
    WAIT_TIME=$((WAIT_TIME + SLEEP_INTERVAL))
done

if [ $WAIT_TIME -ge $MAX_WAIT ]; then
    echo "❌ Timeout waiting for server to be ready!"
    exit 1
fi

# Now start the worker
echo "🚀 Starting worker process..."
exec python scripts/run_workers.py