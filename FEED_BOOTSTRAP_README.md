# Feed Bootstrap System

Complete guide for populating and managing user feeds in the news aggregation app.

## Quick Start

```bash
# 1. Bootstrap feeds for all users
./scripts/bootstrap_feeds.sh

# 2. Process the content
./scripts/start_workers.sh

# 3. View in browser
open http://localhost:8000/
```

## System Architecture

### Content Flow

```
Scrapers → Content (shared pool) → ContentStatusEntry (user inbox) → User Feed
```

### Content Types & Scrapers

| Type | Scrapers | Scope | Config Source |
|------|----------|-------|---------------|
| **Global** | HackerNews, Reddit, Techmeme | All users | Hardcoded in scrapers |
| **User-Specific** | Substack, Atom, Podcast | Per-user | `UserScraperConfig` table |
| **News** | News aggregators | All users (no inbox) | Various sources |

### Database Tables

- **`contents`**: Shared content pool (no user_id)
- **`user_scraper_configs`**: Per-user feed subscriptions
- **`content_status`**: Maps content to user inboxes (status="inbox")
- **`content_read_status`**: Tracks what users have read
- **`content_favorites`**: User favorites

## Complete Workflow

### 1. Initial Setup (One-time)

```bash
# Install dependencies
uv sync

# Initialize database
python -m alembic upgrade head

# Create admin user (if needed)
# This happens automatically on first Apple Sign In
```

### 2. Add User Feed Subscriptions

Users can subscribe to custom feeds via `UserScraperConfig`:

```bash
# Add a Substack feed for user 1
python scripts/add_user_scraper_config.py \
  --user-id 1 \
  --type substack \
  --feed-url "https://importai.substack.com/feed" \
  --name "Import AI"

# Add a podcast feed
python scripts/add_user_scraper_config.py \
  --user-id 1 \
  --type podcast_rss \
  --feed-url "https://feeds.simplecast.com/54nAGcIl" \
  --name "Lenny's Podcast" \
  --limit 5

# List user's configs
python scripts/add_user_scraper_config.py --user-id 1 --list
```

### 3. Bootstrap Feeds

Run scrapers and populate user inboxes:

```bash
# Bootstrap all users
./scripts/bootstrap_feeds.sh

# Bootstrap specific user
./scripts/bootstrap_feeds.sh --users 1

# Only global scrapers
./scripts/bootstrap_feeds.sh --global-only

# Only user-specific scrapers
./scripts/bootstrap_feeds.sh --user-only

# Debug mode
./scripts/bootstrap_feeds.sh --debug
```

### 4. Process Content

Run workers to extract and summarize content:

```bash
./scripts/start_workers.sh
```

### 5. View Results

- **Web UI**: http://localhost:8000/ (admin login required)
- **API**: `GET /api/content/` (requires JWT token)
- **iOS App**: Configure API endpoint in app settings

## Production Deployment

### Automated Scraping

Schedule the bootstrap script to run periodically:

#### Using cron
```bash
# Add to crontab (every hour)
0 * * * * cd /opt/newsly && ./scripts/bootstrap_feeds.sh >> /var/log/newsly/bootstrap.log 2>&1
```

#### Using Docker Compose
The `docker-compose.yml` includes a `scrapers` service with supercronic:

```yaml
services:
  scrapers:
    build:
      context: .
      dockerfile: Dockerfile.scrapers
    environment:
      - CRON_SCHEDULE=0 * * * *  # Every hour
    command: >
      sh -c "supercronic /app/crontab"
```

Update the crontab to use bootstrap script:
```crontab
# /app/crontab
0 * * * * cd /app && ./scripts/bootstrap_feeds.sh >> /logs/bootstrap.log 2>&1
```

### Continuous Workers

Keep workers running to process content:

```bash
# Using supervisor (recommended)
[program:newsly_workers]
command=/opt/newsly/scripts/start_workers.sh
directory=/opt/newsly
user=newsly
autostart=true
autorestart=true
stderr_logfile=/var/log/newsly/workers.err.log
stdout_logfile=/var/log/newsly/workers.out.log

# Or using Docker Compose
docker-compose up -d workers
```

## Advanced Usage

### Adding Feeds for New Users

When a new user signs up:

1. **Automatic**: If using iOS app with Apple Sign In, user is created automatically
2. **Add default feeds**: Optionally create default `UserScraperConfig` entries
3. **Bootstrap their feed**: Run `./scripts/bootstrap_feeds.sh --users <new_user_id>`

Example script for default feeds:

```python
# scripts/setup_default_feeds.py
from app.core.db import get_db
from app.services.scraper_configs import create_user_scraper_config, CreateUserScraperConfig

DEFAULT_FEEDS = [
    {
        "type": "substack",
        "url": "https://importai.substack.com/feed",
        "name": "Import AI",
    },
    {
        "type": "podcast_rss",
        "url": "https://feeds.simplecast.com/54nAGcIl",
        "name": "Lenny's Podcast",
    },
]

def setup_default_feeds(user_id: int):
    with get_db() as db:
        for feed in DEFAULT_FEEDS:
            config = CreateUserScraperConfig(
                scraper_type=feed["type"],
                display_name=feed["name"],
                config={"feed_url": feed["url"], "limit": 10},
            )
            try:
                create_user_scraper_config(db, user_id, config)
                print(f"✓ Added {feed['name']}")
            except ValueError as e:
                print(f"✗ {feed['name']}: {e}")
```

### Bulk Operations

```bash
# Bootstrap all users in batches
for user_id in 1 2 3 4 5; do
  ./scripts/bootstrap_feeds.sh --users $user_id
  sleep 5  # Rate limiting
done

# Re-scrape all user-specific feeds
./scripts/bootstrap_feeds.sh --user-only

# Refresh global content for all users
./scripts/bootstrap_feeds.sh --global-only
```

### Monitoring

Check bootstrap statistics:

```bash
# View recent bootstrap events
python -c "
from app.core.db import get_db
from app.models.schema import EventLog
from datetime import datetime, timedelta

with get_db() as db:
    events = db.query(EventLog).filter(
        EventLog.event_type == 'bootstrap_user_feeds',
        EventLog.created_at >= datetime.utcnow() - timedelta(days=1)
    ).order_by(EventLog.created_at.desc()).limit(10).all()

    for event in events:
        print(f'{event.created_at}: {event.status} - {event.data}')
"

# Check inbox sizes
python scripts/dump_system_stats.py
```

## Troubleshooting

### No content in user feeds

1. Check if user has configs:
   ```bash
   python scripts/add_user_scraper_config.py --user-id 1 --list
   ```

2. Check if bootstrap created inbox entries:
   ```sql
   SELECT COUNT(*) FROM content_status WHERE user_id = 1 AND status = 'inbox';
   ```

3. Check scraper errors:
   ```bash
   tail -f logs/errors/substack_scraper_*.jsonl
   ```

### Duplicate content

- Duplicates are automatically handled via unique constraint on `(url, content_type)`
- Duplicate events are logged but don't cause errors
- Check logs for `"URL already exists"` messages

### Feed not updating

1. Check if feed is active:
   ```sql
   SELECT * FROM user_scraper_configs WHERE is_active = true;
   ```

2. Test feed URL manually:
   ```bash
   curl -I "https://example.com/feed"
   ```

3. Check scraper logs for parsing errors

### Performance issues

- **Many users**: Use `--users` flag to bootstrap incrementally
- **Large feeds**: Adjust `limit` in feed config
- **Slow scrapers**: Run with `--debug` to identify bottlenecks

## Migration from Old System

If migrating from session-based to user-based feeds:

```bash
# Use the migration script
python scripts/migrate_session_to_user.py

# Then bootstrap feeds
./scripts/bootstrap_feeds.sh
```

## API Integration

### iOS App

The iOS app fetches content via `/api/content/`:

```swift
// Automatically filtered to user's inbox
APIClient.shared.getContent(contentType: .article, limit: 25)
```

The API automatically:
1. Filters by user's JWT token
2. Joins with `content_status` to show only inbox items
3. Marks read status from `content_read_status`
4. Shows favorites from `content_favorites`

### Adding Feeds via API

Create an endpoint to add feeds from the app:

```python
# app/routers/api/scraper_configs.py
@router.post("/scraper-configs")
async def add_scraper_config(
    current_user: Annotated[User, Depends(get_current_user)],
    config: CreateUserScraperConfig,
):
    with get_db() as db:
        new_config = create_user_scraper_config(db, current_user.id, config)
        return new_config
```

## Best Practices

1. **Schedule regular bootstraps**: Every 1-2 hours for active feeds
2. **Monitor errors**: Check error logs daily
3. **Limit feed items**: Keep `limit` between 5-20 to avoid overload
4. **Rate limiting**: Add delays between scraper runs if needed
5. **User feedback**: Let users report broken feeds via app
6. **Cleanup old content**: Periodically archive old read items

## Scripts Reference

| Script | Purpose |
|--------|---------|
| `bootstrap_feeds.sh` | Main bootstrap wrapper (recommended) |
| `bootstrap_user_feeds.py` | Bootstrap implementation |
| `add_user_scraper_config.py` | Manage user feed subscriptions |
| `run_scrapers.py` | Run scrapers without inbox management |
| `start_workers.sh` | Start content processors |
| `dump_system_stats.py` | View statistics |

## Environment Variables

```bash
# Required in .env
DATABASE_URL=sqlite:///./news_app.db  # or postgresql://...
JWT_SECRET_KEY=your-secret-key
ADMIN_PASSWORD=your-admin-password

# Optional scraper configs
SUBSTACK_CONFIG_PATH=config/substack.yml
PODCAST_CONFIG_PATH=config/podcasts.yml
```

## Related Documentation

- `scripts/BOOTSTRAP_GUIDE.md` - Detailed bootstrap guide
- `CLAUDE.md` - Complete project architecture
- `docs/plans/` - Implementation plans
- `README.md` - General project README
