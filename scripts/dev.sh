#!/bin/bash
# Unified development script - starts services in background with combined logging

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
LOG_FILE="$PROJECT_ROOT/logs/dev.log"
PID_FILE="$PROJECT_ROOT/logs/dev.pids"

cd "$PROJECT_ROOT"

# Ensure logs directory exists
mkdir -p "$PROJECT_ROOT/logs"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

usage() {
    echo "Usage: $0 [options] [services...]"
    echo ""
    echo "Services: server, workers, scrapers (or 'all')"
    echo ""
    echo "Options:"
    echo "  -k, --kill     Kill running dev services"
    echo "  -s, --status   Show status of dev services"
    echo "  -h, --help     Show this help"
    echo ""
    echo "Examples:"
    echo "  $0                    # Interactive - choose services"
    echo "  $0 all                # Start all services"
    echo "  $0 server workers     # Start specific services"
    echo "  $0 -k                 # Kill all dev services"
}

kill_services() {
    echo -e "${YELLOW}Stopping dev services...${NC}"
    if [ -f "$PID_FILE" ]; then
        while read -r pid name; do
            if kill -0 "$pid" 2>/dev/null; then
                echo "  Stopping $name (PID $pid)"
                kill "$pid" 2>/dev/null || true
            fi
        done < "$PID_FILE"
        rm -f "$PID_FILE"
        echo -e "${GREEN}Done${NC}"
    else
        echo "No PID file found. Checking for orphan processes..."
        pkill -f "uvicorn app.main:app" 2>/dev/null && echo "  Killed server" || true
        pkill -f "run_workers.py" 2>/dev/null && echo "  Killed workers" || true
        pkill -f "run_scrapers.py" 2>/dev/null && echo "  Killed scrapers" || true
    fi
}

show_status() {
    echo -e "${BLUE}Dev services status:${NC}"
    if [ -f "$PID_FILE" ]; then
        while read -r pid name; do
            if kill -0 "$pid" 2>/dev/null; then
                echo -e "  ${GREEN}●${NC} $name (PID $pid) - running"
            else
                echo -e "  ${RED}●${NC} $name (PID $pid) - dead"
            fi
        done < "$PID_FILE"
    else
        echo "  No services tracked"
    fi
}

start_service() {
    local name=$1
    local cmd=$2

    echo -e "${BLUE}Starting $name...${NC}"

    # Run command, prefix each line with service name, append to log
    (
        $cmd 2>&1 | while IFS= read -r line; do
            echo "[$(date '+%H:%M:%S')] [$name] $line"
        done
    ) >> "$LOG_FILE" &

    local pid=$!
    echo "$pid $name" >> "$PID_FILE"
    echo -e "  ${GREEN}Started${NC} (PID $pid)"
}

# Parse options
while [[ $# -gt 0 ]]; do
    case $1 in
        -k|--kill)
            kill_services
            exit 0
            ;;
        -s|--status)
            show_status
            exit 0
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        -*)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
        *)
            break
            ;;
    esac
done

# Collect services to start
SERVICES=("$@")

# If no services specified, show interactive menu
if [ ${#SERVICES[@]} -eq 0 ]; then
    echo -e "${BLUE}Select services to start:${NC}"
    echo "  1) All (server + workers + scrapers)"
    echo "  2) Server only"
    echo "  3) Server + Workers"
    echo "  4) Workers only"
    echo "  5) Scrapers only"
    echo ""
    read -r -p "Choice [1-5]: " choice

    case $choice in
        1) SERVICES=(server workers scrapers) ;;
        2) SERVICES=(server) ;;
        3) SERVICES=(server workers) ;;
        4) SERVICES=(workers) ;;
        5) SERVICES=(scrapers) ;;
        *) echo "Invalid choice"; exit 1 ;;
    esac
fi

# Expand 'all'
if [[ " ${SERVICES[*]} " =~ " all " ]]; then
    SERVICES=(server workers scrapers)
fi

# Kill existing services first
kill_services 2>/dev/null || true

# Clear log file
> "$LOG_FILE"
rm -f "$PID_FILE"

# Activate venv if available
if [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
    source "$PROJECT_ROOT/.venv/bin/activate"
fi

echo ""
echo -e "${BLUE}Starting services: ${SERVICES[*]}${NC}"
echo -e "Log file: $LOG_FILE"
echo ""

# Start each service
for service in "${SERVICES[@]}"; do
    case $service in
        server)
            start_service "server" "python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
            ;;
        workers)
            start_service "workers" "python scripts/run_workers.py --stats-interval 60"
            ;;
        scrapers)
            start_service "scrapers" "python scripts/run_scrapers.py"
            ;;
        *)
            echo -e "${RED}Unknown service: $service${NC}"
            ;;
    esac
done

echo ""
echo -e "${GREEN}All services started!${NC}"
echo -e "Press ${YELLOW}Ctrl+C${NC} to stop tailing (services keep running)"
echo -e "Run ${YELLOW}$0 -k${NC} to stop all services"
echo ""
echo "--- Tailing $LOG_FILE ---"
echo ""

# Tail the log file
tail -f "$LOG_FILE"
