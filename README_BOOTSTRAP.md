# Feed Bootstrap System

## TL;DR

```bash
# Populate user inboxes from existing content
./scripts/bootstrap_feeds.sh --users 1 --days 30
```

## What Is This?

A script that creates `ContentStatusEntry` records to add existing content from the shared pool into user inboxes.

**This does NOT run scrapers.** For scraping, use `python scripts/run_scrapers.py`.

## The Three-Step Pipeline

```
1. SCRAPE  → python scripts/run_scrapers.py    → Populate contents table
2. BOOTSTRAP → ./scripts/bootstrap_feeds.sh    → Create inbox entries
3. PROCESS → ./scripts/start_workers.sh        → Extract & summarize
```

## Quick Start

```bash
# Bootstrap all users with all existing content
./scripts/bootstrap_feeds.sh

# Bootstrap specific user with recent content
./scripts/bootstrap_feeds.sh --users 1 --days 7

# Bootstrap only articles
./scripts/bootstrap_feeds.sh --content-types article
```

## When To Use

- **New user signs up** → Bootstrap their inbox with existing content
- **User joins mid-stream** → Backfill their feed with historical content
- **Reset user feed** → Clear and rebuild from scratch
- **After bulk import** → Distribute imported content to user inboxes

## Common Commands

| Command | Purpose |
|---------|---------|
| `./scripts/bootstrap_feeds.sh` | Bootstrap all users |
| `./scripts/bootstrap_feeds.sh --users 42` | Bootstrap specific user |
| `./scripts/bootstrap_feeds.sh --days 7` | Only content from last 7 days |
| `python scripts/add_user_scraper_config.py --user-id 1 --list` | List user's feed subscriptions |

## How It Works

```
┌──────────────┐
│ Contents     │  8,000 items in shared pool
│ (no user_id) │  (populated by scrapers)
└──────┬───────┘
       │
       │ bootstrap_feeds.sh creates mappings
       ↓
┌──────────────┐
│ Content      │  Per-user inbox
│ Status Entry │  (user_id → content_id)
└──────┬───────┘
       │
       │ API filters by user_id
       ↓
┌──────────────┐
│ User's Feed  │  What they see in app
└──────────────┘
```

## Files

- `scripts/bootstrap_user_feeds.py` - Main implementation
- `scripts/bootstrap_feeds.sh` - Shell wrapper
- `scripts/add_user_scraper_config.py` - Manage user feed subscriptions
- `scripts/QUICK_REFERENCE.md` - Detailed command reference
- `BOOTSTRAP_SUMMARY.md` - Complete implementation summary

## Documentation

- Quick commands: `scripts/QUICK_REFERENCE.md`
- Full details: `BOOTSTRAP_SUMMARY.md`
- Project docs: `CLAUDE.md`

## Need Help?

```bash
# See all options
python scripts/bootstrap_user_feeds.py --help

# Check user's inbox
python -c "
from app.core.db import get_db
from app.models.schema import ContentStatusEntry
with get_db() as db:
    count = db.query(ContentStatusEntry).filter_by(user_id=1, status='inbox').count()
    print(f'User 1: {count} items in inbox')
"
```
