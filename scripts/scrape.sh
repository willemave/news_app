#!/bin/bash
# Run scrapers and process content

WORKERS=${1:-4}

echo "Running scrapers and processing with $WORKERS workers..."

python scripts/run_scrapers_unified.py --max-workers $WORKERS