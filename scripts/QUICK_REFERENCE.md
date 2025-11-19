# Feed Bootstrap Quick Reference

## What Does Bootstrap Do?

**Bootstrap creates `ContentStatusEntry` records** to add existing content from the shared pool into user inboxes. It does **NOT** run scrapers.

## Workflow Separation

| Task | Script | What It Does |
|------|--------|--------------|
| **Scrape** | `python scripts/run_scrapers.py` | Fetch new content → `contents` table |
| **Bootstrap** | `./scripts/bootstrap_feeds.sh` | Map content to users → `content_status` table |
| **Process** | `./scripts/start_workers.sh` | Extract/summarize content |

## Common Commands

```bash
# 1. Bootstrap all users with existing content
./scripts/bootstrap_feeds.sh

# 2. Bootstrap specific user
./scripts/bootstrap_feeds.sh --users 1

# 3. Bootstrap with recent content only
./scripts/bootstrap_feeds.sh --days 7

# 4. Check user's inbox size
python -c "
from app.core.db import get_db
from app.models.schema import ContentStatusEntry
with get_db() as db:
    count = db.query(ContentStatusEntry).filter_by(user_id=1, status='inbox').count()
    print(f'User 1 has {count} items in inbox')
"
```

## Bootstrap Options

```bash
# All users, all content
./scripts/bootstrap_feeds.sh

# Specific user
./scripts/bootstrap_feeds.sh --users 1

# Multiple users
./scripts/bootstrap_feeds.sh --users 1 2 3

# Only recent content
./scripts/bootstrap_feeds.sh --days 7

# Only specific content types
./scripts/bootstrap_feeds.sh --content-types article podcast

# Only completed content
./scripts/bootstrap_feeds.sh --statuses completed

# Combine filters
./scripts/bootstrap_feeds.sh --users 1 --days 30 --content-types article
```

## User Feed Subscriptions

Manage user-specific feed configurations:

```bash
# Add a Substack feed
python scripts/add_user_scraper_config.py \
  --user-id 1 --type substack \
  --feed-url "https://importai.substack.com/feed" \
  --name "Import AI"

# Add a podcast feed
python scripts/add_user_scraper_config.py \
  --user-id 1 --type podcast_rss \
  --feed-url "https://feeds.simplecast.com/54nAGcIl" \
  --name "Lenny's Podcast"

# List user's feeds
python scripts/add_user_scraper_config.py --user-id 1 --list
```

## Complete Workflows

### New User Onboarding
```bash
# User signs up → get their user_id (e.g., 42)

# Add to existing content from last 30 days
./scripts/bootstrap_feeds.sh --users 42 --days 30
```

### Daily Operation
```bash
# 1. Scrape new content (scheduled: hourly)
python scripts/run_scrapers.py

# 2. Bootstrap new content to user inboxes
./scripts/bootstrap_feeds.sh --days 1

# 3. Workers process continuously
./scripts/start_workers.sh
```

### User Adds New Feed Subscription
```bash
# User subscribes via app → creates UserScraperConfig

# 1. Run scrapers to fetch from new feed
python scripts/run_scrapers.py --scrapers substack

# 2. Content automatically added to user's inbox
#    (happens during scraping via ensure_inbox_status)
```

### Reset User Feed
```bash
# 1. Clear inbox
python -c "
from app.core.db import get_db
from app.models.schema import ContentStatusEntry
with get_db() as db:
    db.query(ContentStatusEntry).filter_by(user_id=1).delete()
    db.commit()
    print('Cleared inbox for user 1')
"

# 2. Rebuild from scratch
./scripts/bootstrap_feeds.sh --users 1 --days 7
```

## Database Queries

```sql
-- Check user's inbox size
SELECT COUNT(*) FROM content_status
WHERE user_id = 1 AND status = 'inbox';

-- Check user's feed configs
SELECT scraper_type, display_name, feed_url, is_active
FROM user_scraper_configs
WHERE user_id = 1;

-- Check content by status
SELECT status, COUNT(*)
FROM contents
GROUP BY status;

-- Find recent content
SELECT id, title, content_type, source, created_at
FROM contents
WHERE status = 'completed'
ORDER BY created_at DESC
LIMIT 10;

-- Check which users have content
SELECT user_id, COUNT(*) as inbox_count
FROM content_status
WHERE status = 'inbox'
GROUP BY user_id;
```

## Monitoring

```bash
# System stats
python scripts/dump_system_stats.py

# Recent content count
python -c "
from app.core.db import get_db
from app.models.schema import Content
from datetime import datetime, timedelta
with get_db() as db:
    cutoff = datetime.utcnow() - timedelta(days=1)
    count = db.query(Content).filter(Content.created_at >= cutoff).count()
    print(f'{count} items created in last 24 hours')
"

# User inbox breakdown
python -c "
from app.core.db import get_db
from app.models.schema import ContentStatusEntry, User
from sqlalchemy import func
with get_db() as db:
    results = db.query(
        ContentStatusEntry.user_id,
        User.email,
        func.count(ContentStatusEntry.id).label('count')
    ).join(User).filter(
        ContentStatusEntry.status == 'inbox'
    ).group_by(ContentStatusEntry.user_id, User.email).all()

    for user_id, email, count in results:
        print(f'User {user_id} ({email}): {count} items')
"
```

## Troubleshooting

| Problem | Diagnosis | Solution |
|---------|-----------|----------|
| No content in feed | Check `contents` table | Run `python scripts/run_scrapers.py` |
| Content exists but not in inbox | Check `content_status` | Run `./scripts/bootstrap_feeds.sh --users 1` |
| User has no feeds | Check `user_scraper_configs` | Add configs with `add_user_scraper_config.py` |
| Bootstrap adds no items | Content already in inbox | This is normal (check "Skipped" count) |
| Slow bootstrap | Too much content | Use `--days` to limit date range |

## Production Scheduling

```bash
# Crontab example
# Scrape every hour
0 * * * * cd /opt/newsly && python scripts/run_scrapers.py >> /var/log/newsly/scrapers.log 2>&1

# Bootstrap 5 minutes after scraping (daily content)
5 * * * * cd /opt/newsly && ./scripts/bootstrap_feeds.sh --days 1 >> /var/log/newsly/bootstrap.log 2>&1

# Workers run continuously (via supervisor/systemd)
```

## Key Points

1. **Bootstrap ≠ Scraping**: Bootstrap only creates inbox entries from existing content
2. **Idempotent**: Safe to run multiple times (skips duplicates)
3. **Per-User**: Each user has their own inbox mapping
4. **News Skipped**: News items don't need inbox entries (shown to all users)
5. **Automatic**: User-specific scrapers automatically create inbox entries
