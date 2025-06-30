web: .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
cron: cron -f
worker: .venv/bin/python scripts/run_worker.py