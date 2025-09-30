# Deployment Checklist for Supervisor Setup

## What Was Fixed

### 1. Alembic Database URL Loading
- **File**: `alembic/env.py`
- **Change**: Now uses `app.core.settings.get_settings()` instead of `os.getenv("DATABASE_URL")`
- **Why**: Pydantic's `BaseSettings` automatically loads `.env` files, while `os.getenv()` only reads shell environment variables
- **Result**: Migrations now work reliably when `.env` file exists in project root

### 2. Start Scripts Validation
- **Files**: `scripts/start_server.sh`, `scripts/start_workers.sh`, `scripts/start_scrapers.sh`
- **Change**: Added explicit `.env` file existence check
- **Why**: Provides clear error messages if `.env` is missing or in wrong location
- **Result**: Faster debugging when configuration is wrong

### 3. Supervisor Configuration
- **File**: `supervisor.conf` (template for deployment)
- **Change**: Removed `/bin/bash -lc` wrapper, added explicit PATH
- **Why**: Login shells can cause unexpected behavior; explicit PATH is more reliable
- **Result**: Cleaner, more predictable process management

## Migration Strategy

### Which Scripts Run Migrations?
- ✅ **start_server.sh**: Runs `alembic upgrade head` before starting server
- ✅ **start_workers.sh**: Runs `alembic upgrade head` before starting workers
- ✅ **start_scrapers.sh**: Runs `alembic upgrade head` before starting scrapers

### Why All Scripts Run Migrations?
- **Idempotent**: Alembic's `upgrade head` is safe to run multiple times
- **Order-independent**: Any service can start first and ensure schema is current
- **Robustness**: No dependency on startup order; each service verifies DB state
- **Race-safe**: Alembic uses database locks to prevent concurrent migrations
- Whichever script runs first will apply migrations; others will see "already up-to-date"

## Server Deployment Steps

### 1. Verify File Locations on Server
```bash
ssh newsapp@your-server

# Verify project location
cd /opt/news_app
pwd  # Should show: /opt/news_app

# Verify .env file exists in project root
ls -la .env  # Should exist at /opt/news_app/.env

# Verify .env has DATABASE_URL
grep DATABASE_URL .env
```

### 2. Update Supervisor Configuration
```bash
# On server, become root or use sudo
sudo cp /opt/news_app/supervisor.conf /etc/supervisor/conf.d/news_app.conf

# Reload supervisor to read new config
sudo supervisorctl reread
sudo supervisorctl update
```

### 3. Deploy Updated Code
```bash
# On server as newsapp user
cd /opt/news_app
git pull origin main

# Verify the updated alembic/env.py
head -20 alembic/env.py  # Should import get_settings
```

### 4. Test Migrations Manually
```bash
cd /opt/news_app
source .venv/bin/activate

# Test that settings load correctly
python -c "from app.core.settings import get_settings; print(get_settings().database_url)"

# Test that alembic can find DATABASE_URL
python -m alembic current

# Run migrations manually to verify
python -m alembic upgrade head
```

### 5. Restart Services
```bash
# Restart all services to pick up changes
sudo supervisorctl restart news_app_server
sudo supervisorctl restart news_app_workers
sudo supervisorctl restart news_app_scrapers

# Check status
sudo supervisorctl status

# Check logs for any errors
sudo tail -f /var/log/news_app/server.log
sudo tail -f /var/log/news_app/server.err.log
```

## Troubleshooting

### Migrations Still Fail
```bash
# Check that .env is in the right place
ls -la /opt/news_app/.env

# Verify DATABASE_URL is set correctly
cd /opt/news_app
source .venv/bin/activate
python -c "from app.core.settings import get_settings; print(get_settings().database_url)"

# Check alembic can import app modules
python -c "from app.models.schema import Base; print('OK')"

# Run migrations with verbose output
cd /opt/news_app
python -m alembic -v upgrade head
```

### Server Won't Start
```bash
# Check supervisor logs
sudo tail -100 /var/log/news_app/server.err.log

# Try running start script manually
cd /opt/news_app
./scripts/start_server.sh

# Check if port 8000 is already in use
sudo netstat -tlnp | grep 8000
```

### Workers Won't Start
```bash
# Check supervisor logs
sudo tail -100 /var/log/news_app/workers.err.log

# Verify database is accessible
cd /opt/news_app
source .venv/bin/activate
python -c "from app.core.db import init_db; init_db(); print('OK')"

# Try running workers script manually
./scripts/start_workers.sh --debug --max-tasks 1
```

## Quick Reference

### Supervisor Commands
```bash
# View status
sudo supervisorctl status

# Restart specific service
sudo supervisorctl restart news_app_server

# Restart all services
sudo supervisorctl restart news_app_server news_app_workers news_app_scrapers

# View logs
sudo supervisorctl tail -f news_app_server
sudo supervisorctl tail -f news_app_server stderr

# Stop/start services
sudo supervisorctl stop news_app_workers
sudo supervisorctl start news_app_workers
```

### Manual Service Testing
```bash
cd /opt/news_app
source .venv/bin/activate

# Test server (with migrations)
./scripts/start_server.sh

# Test workers (in another terminal)
./scripts/start_workers.sh --stats-interval 60

# Test scrapers (in another terminal)
./scripts/start_scrapers.sh --show-stats
```

## Key Files Reference

- `/opt/news_app/.env` - Environment variables (DATABASE_URL, API keys)
- `/opt/news_app/alembic/env.py` - Alembic configuration (loads from settings)
- `/opt/news_app/app/core/settings.py` - Pydantic settings (loads .env)
- `/opt/news_app/scripts/start_server.sh` - Server startup (runs migrations)
- `/opt/news_app/scripts/start_workers.sh` - Workers startup
- `/opt/news_app/scripts/start_scrapers.sh` - Scrapers startup
- `/etc/supervisor/conf.d/news_app.conf` - Supervisor configuration
- `/var/log/news_app/*.log` - Application logs