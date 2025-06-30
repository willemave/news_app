#!/bin/bash
# Shell script wrapper that runs migrations before starting the server

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Change to project root
cd "$PROJECT_ROOT"

# Activate virtual environment
source .venv/bin/activate

# Run the Python startup script
exec python scripts/start_server.py "$@"