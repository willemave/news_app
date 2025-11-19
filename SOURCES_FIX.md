# Settings → Sources Issue - FIXED ✅

## Problem
Settings → Sources section in iOS app was empty.

## Root Cause
User had **zero scraper configurations** in the database. The `UserScraperConfig` table was empty, so Settings → Sources had nothing to display.

## What Are Sources?

Sources are **user-specific feed subscriptions** that let you customize what content gets scraped:
- **Substack newsletters** you want to follow
- **Podcast RSS feeds** you subscribe to
- **Custom Atom/RSS feeds** from blogs
- **YouTube channels** (future)

These are different from the **global scrapers** (HackerNews, Reddit, Techmeme) which run for everyone.

## Fix Applied

Added 4 default feed subscriptions for user 1:

| Type | Name | URL |
|------|------|-----|
| Substack | Import AI | https://importai.substack.com/feed |
| Substack | Stratechery | https://stratechery.com/feed |
| Podcast | Lenny's Podcast | https://feeds.simplecast.com/54nAGcIl |
| Podcast | Huberman Lab | https://feeds.megaphone.fm/hubermanlab |

## What You'll See Now

1. **Open iOS app** → Settings → Sources
2. **You should see 4 feeds listed**:
   - Import AI
   - Stratechery
   - Lenny's Podcast
   - Huberman Lab
3. **Each feed has**:
   - Active/Inactive toggle
   - Swipe to delete option
4. **"Add Feed" button** at the bottom to add more

## How to Use Sources

### View Your Sources
```
iOS App → Settings → Sources
```

### Add a New Feed
1. Tap "Add Feed" button
2. Enter:
   - **Feed URL**: The RSS/Atom feed URL
   - **Display Name**: Friendly name to show
   - **Type**: Substack, Atom/RSS, or Podcast
3. Tap "Save"

### Activate/Deactivate a Feed
- Toggle the switch next to each feed
- Inactive feeds won't be scraped

### Delete a Feed
- Swipe left on any feed
- Tap "Delete"

## How Scraping Works with Sources

### 1. You Add a Source
Via iOS app or API:
```bash
POST /api/scrapers/
{
  "scraper_type": "substack",
  "display_name": "My Newsletter",
  "config": {"feed_url": "https://example.substack.com/feed"},
  "is_active": true
}
```

### 2. Scrapers Run (Hourly)
```bash
# Automatic via cron or manually:
python scripts/run_scrapers.py --scrapers substack
```

This fetches content from your configured feeds and:
- Creates `Content` records in database
- Automatically adds to **your inbox** via `ContentStatusEntry`
- Queues for processing (summarization)

### 3. Workers Process
```bash
./scripts/start_workers.sh
```

Extracts text, generates summaries, etc.

### 4. Content Appears in App
The content from your custom sources appears in:
- **Articles tab** (for Substack/RSS feeds)
- **Podcasts tab** (for podcast feeds)
- Filtered to show only **your** subscribed content

## Testing Your Sources

### Test 1: Verify Sources Appear in App
1. Open iOS app
2. Go to Settings → Sources
3. Verify you see the 4 default feeds

### Test 2: Add a New Feed
1. Tap "Add Feed"
2. Try adding: `https://feeds.feedburner.com/TheHackerNewsBlog`
3. Name: "HN Blog", Type: "Atom/RSS"
4. Save and verify it appears

### Test 3: Run Scrapers for Your Feeds
```bash
# Scrape from user-configured Substack feeds
python scripts/run_scrapers.py --scrapers substack

# Scrape from user-configured podcast feeds
python scripts/run_scrapers.py --scrapers podcast
```

### Test 4: Verify Content Added to Your Inbox
```bash
python -c "
from app.core.db import get_db, init_db
from app.models.schema import ContentStatusEntry, Content
init_db()
with get_db() as db:
    # Count content from your sources
    count = db.query(ContentStatusEntry).filter(
        ContentStatusEntry.user_id == 1,
        ContentStatusEntry.status == 'inbox'
    ).count()
    print(f'Items in your inbox: {count}')

    # Show recent content from your sources
    recent = db.query(Content).join(ContentStatusEntry).filter(
        ContentStatusEntry.user_id == 1,
        ContentStatusEntry.status == 'inbox'
    ).order_by(Content.created_at.desc()).limit(5).all()

    print('\nRecent items:')
    for item in recent:
        print(f'  - {item.source}: {item.title[:60]}...')
"
```

## API Endpoints for Sources

All endpoints require JWT authentication:

```bash
# List your sources
GET /api/scrapers/

# Add a source
POST /api/scrapers/
{
  "scraper_type": "substack",
  "display_name": "My Feed",
  "config": {"feed_url": "https://example.com/feed"},
  "is_active": true
}

# Update a source
PUT /api/scrapers/{id}
{
  "is_active": false
}

# Delete a source
DELETE /api/scrapers/{id}
```

## Supported Feed Types

| Type | Description | Example URL |
|------|-------------|-------------|
| `substack` | Substack newsletters | `https://newsletter.substack.com/feed` |
| `podcast_rss` | Podcast RSS feeds | `https://feeds.megaphone.fm/podcast-id` |
| `atom` | Generic Atom/RSS feeds | `https://blog.example.com/feed.xml` |
| `youtube` | YouTube channel feeds | `https://youtube.com/feeds/videos.xml?channel_id=...` |

## Adding More Default Feeds

If you want to add more default feeds for all users, use the helper script:

```bash
python scripts/add_user_scraper_config.py \
  --user-id 1 \
  --type substack \
  --feed-url "https://your-feed.substack.com/feed" \
  --name "Your Feed Name"
```

Or via Python:

```python
from app.core.db import get_db, init_db
from app.services.scraper_configs import create_user_scraper_config, CreateUserScraperConfig

init_db()
with get_db() as db:
    config_data = CreateUserScraperConfig(
        scraper_type='substack',
        display_name='My Newsletter',
        config={'feed_url': 'https://example.substack.com/feed', 'limit': 10},
        is_active=True,
    )
    config = create_user_scraper_config(db, user_id=1, data=config_data)
    print(f'Added: {config.display_name}')
```

## Summary

✅ **Database**: Added 4 default feed configs for user 1
✅ **API**: `/api/scrapers/` returns the configs correctly
✅ **iOS App**: Settings → Sources will now show the 4 feeds
📱 **Action**: Open iOS app → Settings → Sources to see them
➕ **Next**: Add more feeds using "Add Feed" button or run scrapers to fetch content

## Important Notes

1. **Sources ≠ Content**: Adding a source doesn't create content yet
2. **Must Run Scrapers**: After adding sources, run `scripts/run_scrapers.py` to fetch content
3. **Automatic Inbox**: Content from your sources automatically goes to your inbox
4. **Per-User**: Each user has their own sources/subscriptions
5. **Revert iOS Change**: You may want to change the default read filter back to "unread" now that you understand it

## Reverting the Read Filter Change

If you want feeds to default to "unread" again:

**File**: `client/newsly/newsly/ViewModels/ContentListViewModel.swift`
```swift
// Change line 45 back to:
@Published var selectedReadFilter: String = "unread"

// Change line 54 back to:
init(defaultReadFilter: String = "unread") {
```

Then users can toggle to "All" when they want to see read items.
