#!/bin/bash
# Check and apply Alembic migrations for deployment/CI.

set -euo pipefail

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Change to project root
cd "$PROJECT_ROOT"
echo "Working directory: $(pwd)"

# If there is a project venv, use it, otherwise assume the current env is correct
if [ -f ".venv/bin/activate" ]; then
    echo "Activating project .venv"
    # shellcheck source=/dev/null
    source .venv/bin/activate
else
    echo "No .venv found, using current Python environment: $(python -c 'import sys; print(sys.executable)')"
fi

# Check if alembic.ini exists
if [ ! -f "alembic.ini" ]; then
    echo "ERROR: alembic.ini not found. Please initialize Alembic first."
    exit 1
fi

# Validate required settings via Pydantic (loads .env via python-dotenv)
python <<'PY'
from app.core.settings import get_settings

try:
    get_settings()
except Exception as exc:
    raise SystemExit(f"ERROR: Invalid or missing settings for migrations: {exc}") from exc
PY

echo ""
echo "Checking current Alembic revision..."
python -m alembic current

echo ""
echo "Alembic head revision(s)..."
python -m alembic heads

echo ""
echo "Running database migrations (upgrade head)..."
python -m alembic upgrade head

echo ""
echo "Migrations completed. Current revision:"
python -m alembic current
