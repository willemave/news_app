#!/bin/bash
# Startup script for running task processing workers.
# This processes scraped content through the sequential task processor.

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
MAX_TASKS=""
DEBUG_FLAG=""
STATS_INTERVAL="30"

while [[ $# -gt 0 ]]; do
    case $1 in
        --debug)
            DEBUG_FLAG="--debug"
            shift
            ;;
        --max-tasks)
            MAX_TASKS="--max-tasks $2"
            shift 2
            ;;
        --stats-interval)
            STATS_INTERVAL="$2"
            shift 2
            ;;
        --no-stats)
            STATS_INTERVAL="0"
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --debug              Enable debug logging"
            echo "  --max-tasks N        Process at most N tasks then exit"
            echo "  --stats-interval N   Show stats every N seconds (default: 30)"
            echo "  --no-stats           Disable periodic stats display"
            echo "  -h, --help           Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Run '$0 --help' for usage information"
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

# Check queue status
echo ""
echo "📊 Checking task queue status..."
QUEUE_CHECK=$(python -c "
from app.core.db import init_db
from app.services.queue import get_queue_service
init_db()
queue = get_queue_service()
stats = queue.get_queue_stats()
pending = sum(stats.get('pending_by_type', {}).values())
print(f'pending:{pending}')
print(f'completed:{stats.get(\"completed\", 0)}')
print(f'failed:{stats.get(\"failed\", 0)}')
" 2>/dev/null)

if [ -z "$QUEUE_CHECK" ]; then
    echo "⚠️  Could not check queue status. Proceeding anyway..."
else
    PENDING=$(echo "$QUEUE_CHECK" | grep "pending:" | cut -d: -f2)
    COMPLETED=$(echo "$QUEUE_CHECK" | grep "completed:" | cut -d: -f2)
    FAILED=$(echo "$QUEUE_CHECK" | grep "failed:" | cut -d: -f2)
    
    echo "  Pending tasks: $PENDING"
    echo "  Completed: $COMPLETED"
    echo "  Failed: $FAILED"
    
    if [ "$PENDING" = "0" ]; then
        echo ""
        echo "⚠️  No pending tasks in queue!"
        echo "💡 Run './scripts/start_scrapers.sh' first to populate content"
        echo ""
        echo "Do you want to continue anyway? (y/N)"
        read -r response
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            exit 0
        fi
    fi
fi

# Build worker command
WORKER_COMMAND="python scripts/run_workers.py $DEBUG_FLAG $MAX_TASKS --stats-interval $STATS_INTERVAL"

# Show what we're about to run
echo ""
echo "🚀 Starting task processing workers..."

if [ -n "$MAX_TASKS" ]; then
    echo "Max tasks: ${MAX_TASKS#--max-tasks }"
else
    echo "Max tasks: unlimited (run until queue is empty or interrupted)"
fi

if [ -n "$DEBUG_FLAG" ]; then
    echo "Debug mode: ENABLED"
fi

if [ "$STATS_INTERVAL" != "0" ]; then
    echo "Stats interval: every $STATS_INTERVAL seconds"
else
    echo "Stats display: DISABLED"
fi

echo ""
echo "Press Ctrl+C to stop gracefully"
echo ""

# Run the workers
trap 'echo -e "\n\n✋ Workers stopped by user"; exit 0' INT
eval $WORKER_COMMAND || {
    echo ""
    echo "❌ Workers failed"
    exit 1
}

echo ""
echo "✅ Task processing completed!"

# Show final stats
echo ""
echo "📊 Final queue status:"
python -c "
from app.core.db import init_db
from app.services.queue import get_queue_service
init_db()
queue = get_queue_service()
stats = queue.get_queue_stats()
by_status = stats.get('by_status', {})
pending = sum(stats.get('pending_by_type', {}).values())
print(f'  Pending tasks: {pending}')
print(f'  Completed: {by_status.get(\"completed\", 0)}')
print(f'  Failed: {by_status.get(\"failed\", 0)}')
" 2>/dev/null || echo "  Could not retrieve final stats"