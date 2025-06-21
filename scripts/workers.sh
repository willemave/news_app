#!/bin/bash
# Run thread-based task workers

WORKERS=${1:-4}

echo "Starting $WORKERS worker threads..."
echo "Press Ctrl+C to stop"

python run_workers.py $WORKERS