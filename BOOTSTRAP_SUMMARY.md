# Feed Bootstrap Implementation Summary

## What Was Created

A complete feed bootstrap system that populates user inboxes from the existing content pool by creating `ContentStatusEntry` records.

### Core Script

**`scripts/bootstrap_user_feeds.py`** - Populates user inboxes from existing content
- **Does NOT run scrapers** (use `run_scrapers.py` for that)
- Creates `ContentStatusEntry` records to add content to user inboxes
- Supports filtering by:
  - Specific users (`--users 1 2 3`)
  - Time range (`--days 7`)
  - Content types (`--content-types article podcast`)
  - Processing status (`--statuses completed`)
- Provides detailed statistics and event logging

### Helper Scripts

2. **`scripts/bootstrap_feeds.sh`** - Convenient shell wrapper
   - Activates virtual environment
   - Runs bootstrap script with all arguments

3. **`scripts/add_user_scraper_config.py`** - User feed subscription management
   - Add/list user scraper configurations
   - Supports substack, atom, podcast_rss, youtube feed types
   - Validates feed URLs and prevents duplicates

### Documentation

- **`scripts/BOOTSTRAP_GUIDE.md`** - Detailed guide
- **`scripts/QUICK_REFERENCE.md`** - Command cheat sheet
- **`FEED_BOOTSTRAP_README.md`** - Complete workflow documentation (needs updating)

## How It Works

### Architecture

```
┌─────────────────┐
│  run_scrapers   │  Step 1: Populate content pool
│  (separate)     │  Creates Content records
└────────┬────────┘
         │
         v
┌─────────────────┐
│  Contents       │  Shared content pool
│  (no user_id)   │  (url, title, metadata)
│  ~8000 items    │
└────────┬────────┘
         │
         v
┌─────────────────┐  Step 2: Bootstrap (this script)
│  bootstrap_     │  Creates inbox mappings
│  user_feeds.py  │
└────────┬────────┘
         │
         v
┌─────────────────┐
│ ContentStatus   │  Per-user inbox
│ Entry           │  (user_id, content_id, status="inbox")
└────────┬────────┘
         │
         v
┌─────────────────┐
│  User Feed      │  What user sees in their
│  (API/iOS app)  │  feed (via API filter)
└─────────────────┘
```

### Key Concepts

1. **Shared Content Pool**: `contents` table has no user_id - content is shared across all users
2. **User Inbox Mapping**: `content_status` table maps which content appears in each user's inbox
3. **Separation of Concerns**:
   - `run_scrapers.py` → Populates content pool
   - `bootstrap_user_feeds.py` → Populates user inboxes
   - `start_workers.sh` → Processes content (extraction/summarization)

## Usage Examples

### Example 1: Bootstrap New User

```bash
# User signs up with ID 42
# Bootstrap their inbox with existing content
./scripts/bootstrap_feeds.sh --users 42

# Or just content from last 30 days
./scripts/bootstrap_feeds.sh --users 42 --days 30

# Or only articles
./scripts/bootstrap_feeds.sh --users 42 --content-types article
```

### Example 2: Backfill All Users

```bash
# Add all existing content to all user inboxes
./scripts/bootstrap_feeds.sh

# Or just recent content
./scripts/bootstrap_feeds.sh --days 7
```

### Example 3: Complete Workflow

```bash
# 1. Run scrapers to get new content
python scripts/run_scrapers.py

# 2. Bootstrap user inboxes
./scripts/bootstrap_feeds.sh

# 3. Process the content
./scripts/start_workers.sh
```

## Testing

Your current system has:
- **2 active users** (willem.ave@gmail.com, test@example.com)
- **8,040 content items** in the database
- **2,791 items in user 1's inbox** (after running bootstrap)

To test:

```bash
# Bootstrap user 1 with all content
./scripts/bootstrap_feeds.sh --users 1

# Expected output:
#   Found 8040 existing content items
#   Added: N, Skipped: M (items already in inbox)
#   User 1: X items in inbox

# Bootstrap only recent articles
./scripts/bootstrap_feeds.sh --users 1 --days 7 --content-types article
```

## Integration Points

### Complete Content Pipeline

```bash
# Full pipeline for daily operation:

# 1. Scrape new content (cron: hourly)
python scripts/run_scrapers.py

# 2. Bootstrap inboxes (cron: after scraping)
./scripts/bootstrap_feeds.sh --days 1

# 3. Process content (continuous worker)
./scripts/start_workers.sh
```

### With iOS App

The iOS app uses `/api/content/` which:
- Automatically joins with `content_status` table
- Filters by `user_id` from JWT token
- Only shows content with `status="inbox"`
- No app changes needed!

### User-Specific Feeds

Users can subscribe to custom feeds:

```bash
# Add a Substack subscription for user 1
python scripts/add_user_scraper_config.py \
  --user-id 1 \
  --type substack \
  --feed-url "https://importai.substack.com/feed" \
  --name "Import AI"

# Run scrapers to fetch from this feed
python scripts/run_scrapers.py --scrapers substack

# Bootstrap to add to inbox (happens automatically during scraping)
# No need to run bootstrap manually
```

## Common Use Cases

### 1. New User Onboarding

```bash
# User just signed up
USER_ID=42

# Add them to all existing content from last 30 days
./scripts/bootstrap_feeds.sh --users $USER_ID --days 30
```

### 2. Reset User Feed

```bash
# Clear user's inbox
python -c "
from app.core.db import get_db
from app.models.schema import ContentStatusEntry
with get_db() as db:
    db.query(ContentStatusEntry).filter_by(user_id=1).delete()
    db.commit()
"

# Rebuild from scratch
./scripts/bootstrap_feeds.sh --users 1 --days 7
```

### 3. Backfill Historical Content

```bash
# Add all completed articles from last 90 days to all users
./scripts/bootstrap_feeds.sh --days 90 --content-types article --statuses completed
```

## Next Steps

1. **Update documentation** (`FEED_BOOTSTRAP_README.md`) to reflect that bootstrap doesn't run scrapers

2. **Scheduled operation**:
   ```bash
   # Crontab example
   0 * * * * cd /opt/newsly && python scripts/run_scrapers.py
   5 * * * * cd /opt/newsly && ./scripts/bootstrap_feeds.sh --days 1
   ```

3. **Monitor results**:
   ```bash
   python scripts/dump_system_stats.py
   ```

## Files Changed/Added

### New Files
- `scripts/bootstrap_user_feeds.py` - Main implementation (creates inbox entries)
- `scripts/bootstrap_feeds.sh` - Shell wrapper
- `scripts/add_user_scraper_config.py` - Config management
- `scripts/BOOTSTRAP_GUIDE.md` - Detailed guide (needs updating)
- `scripts/QUICK_REFERENCE.md` - Quick reference (needs updating)
- `FEED_BOOTSTRAP_README.md` - Complete documentation (needs updating)
- `BOOTSTRAP_SUMMARY.md` - This file

### No Existing Files Modified
All existing code remains unchanged.

## Summary

You now have a bootstrap system that:
- ✅ Populates user inboxes from existing content pool
- ✅ Does NOT run scrapers (separate concern)
- ✅ Supports filtering by user, date, type, and status
- ✅ Skips duplicates automatically
- ✅ Provides detailed statistics
- ✅ Integrates with existing iOS app (no changes needed)
- ✅ Includes management tools for user configs

### Workflow Separation

| Task | Script | Purpose |
|------|--------|---------|
| Scrape content | `run_scrapers.py` | Populate content pool |
| Populate inboxes | `bootstrap_user_feeds.py` | Create inbox entries |
| Process content | `start_workers.sh` | Extract/summarize |

Ready to use! 🚀
