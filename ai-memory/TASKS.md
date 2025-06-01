# Router and Template Updates for Articles Display

## Phase 1: Update Router and Rename Template
**Phase Goal:** Change the articles router to mount at "/" instead of "/daily" and rename the template file.

### Tasks:
- [x] Update `app/routers/articles.py` to change route from "/daily" to "/"
- [x] Update template reference from "daily_links.html" to "articles.html"
- [x] Rename `templates/daily_links.html` to `templates/articles.html`

### Reference Files:
- `app/routers/articles.py` - Main router file to modify
- `templates/daily_links.html` - Template to rename and update

## Phase 2: Update Template to Display Short Summary
**Phase Goal:** Modify the articles query to join with summaries and update the template to display short_summary.

### Tasks:
- [x] Update SQLAlchemy query in `get_daily_articles` to join Articles with Summaries
- [x] Modify `templates/articles.html` to display title, url, and short_summary
- [x] Add proper null checks for summaries in template
- [x] Test the updated display functionality

### Reference Files:
- `app/models.py` - Review relationship between Articles and Summaries
- `templates/articles.html` - Template to update with summary display

## Phase 3: Update Memory Bank
### Tasks:
- [x] Update `ai-memory/README.md` with changes to router mounting and template structure
- [x] Mark tasks as complete in this file

### Key Learnings/Decisions from this Phase:
- Successfully changed articles router from "/daily" to "/" mounting
- Renamed daily_links.html to articles.html
- Updated template to display title, URL, and short_summary from joined Summaries table
- Fixed multiple import issues by removing raindrop.py and rss.py references
- Updated cron/daily_ingest.py and cron/process_articles.py to use correct imports
- Removed missing links router from main.py
- Server now starts successfully and articles are displayed with summaries
