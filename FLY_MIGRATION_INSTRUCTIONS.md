# Fly.io Database Migration Instructions

## Issue
The worker process is failing with:
```
sqlite3.OperationalError: no such table: processing_tasks
```

## Solution
You need to run the Alembic migration to create the missing `processing_tasks` table.

## Steps to Run Migration on Fly.io

1. First, deploy the latest code (including the new migration file):
   ```bash
   fly deploy
   ```

2. SSH into your Fly.io instance:
   ```bash
   fly ssh console
   ```

3. Once connected, navigate to the app directory:
   ```bash
   cd /app
   ```

4. Activate the virtual environment:
   ```bash
   source .venv/bin/activate
   ```

5. Run the migration:
   ```bash
   alembic upgrade head
   ```

6. Verify the migration was successful:
   ```bash
   alembic current
   ```

7. Exit the SSH session:
   ```bash
   exit
   ```

## Alternative: Run Migration During Deployment

You can also add a migration step to your deployment process by modifying your startup script to run migrations before starting the app. This ensures migrations are always up to date.

Add to your startup script (before starting the app):
```bash
alembic upgrade head
```

## Troubleshooting

If you encounter issues:

1. Check the current migration status:
   ```bash
   fly ssh console -C "cd /app && source .venv/bin/activate && alembic current"
   ```

2. View migration history:
   ```bash
   fly ssh console -C "cd /app && source .venv/bin/activate && alembic history"
   ```

3. Check database tables:
   ```bash
   fly ssh console -C "cd /app && sqlite3 /data/news_app.db '.tables'"
   ```