# UI Template Overhaul - Implementation Tasks

## Phase 1: Cleanup and Removal
- [x] Remove old template files
  - [x] Delete `templates/admin_dashboard.html`
  - [x] Delete `templates/admin_index.html`
  - [x] Delete `templates/partials/article_preview.html`
  - [x] Delete `templates/podcast_detail.html`
  - [x] Delete `templates/podcasts.html`
  - [x] Delete `templates/daily_links.html` (if exists)
  - [x] Keep only `templates/base.html` as starting point

- [x] Remove old API endpoints
  - [x] Delete `app/api/admin.py`
  
  - [x] Archive `app/api/content.py` content for reference (copy useful parts)
  - [x] Delete entire `app/api/` directory after archiving

- [x] Remove old routers that won't be needed
  - [x] Delete `app/routers/admin.py`
  - [x] Delete `app/routers/podcasts.py`
  - [x] Archive `app/routers/articles.py` for reference

- [x] Update `app/main.py` to remove references to deleted routers/APIs

## Phase 2: Create New Router Structure
- [x] Create `app/routers/content.py` - main content listing and detail router
  - [x] Implement `/` route for content list with filters
  - [x] Implement `/content/{content_id}` for detail view
  - [x] Use unified Content model instead of Articles/Links

- [x] Create `app/routers/logs.py` - admin logs viewer
  - [x] Implement `/admin/logs` route
  - [x] List all log files from `logs/` directory
  - [x] Implement `/admin/logs/{filename}` to view specific log content

## Phase 3: Update Base Template
- [x] Modify `templates/base.html`
  - [x] Simplify header - just app name and minimal navigation
  - [x] Remove links to articles/podcasts/admin dashboard
  - [x] Add link to content list (`/`) and logs (`/admin/logs`)
  - [x] Ensure mobile responsiveness with proper viewport meta tags
  - [x] Keep TailwindCSS styling minimal and clean

## Phase 4: Create Content List Template
- [x] Create `templates/content_list.html`
  - [x] Minimalistic design with focus on readability
  - [x] Add filters at top:
    - [x] Content type dropdown (All, Article, Podcast)
    - [x] Date picker or dropdown for date filtering
  - [x] Content items displayed as simple cards:
    - [x] Title (linked to detail page)
    - [x] Content type badge
    - [x] Date
    - [x] Short summary preview (if available)
  - [x] Mobile-first responsive design
  - [x] Use TailwindCSS utility classes

## Phase 5: Create Content Detail Template
- [x] Create `templates/content_detail.html`
  - [x] Clean, readable layout for article/podcast details
  - [x] Metadata section:
    - [x] Title
    - [x] Content type
    - [x] URL (as external link)
    - [x] Created date
    - [x] Status
  - [x] Content sections:
    - [x] Short summary (if available)
    - [x] Detailed summary (if available)
    - [x] For podcasts: show transcript if available in metadata
  - [x] Back button to return to list
  - [x] Mobile-optimized typography and spacing

## Phase 6: Create Admin Logs Template
- [x] Create `templates/logs_list.html`
  - [x] Simple list of log files from `logs/` directory
  - [x] Show filename, size, last modified date
  - [x] Click to view log content

- [x] Create `templates/log_detail.html`  
  - [x] Display log file content in monospace font
  - [x] Add basic search/filter functionality (client-side)
  - [x] Download button for log file
  - [x] Back to logs list button

## Phase 7: Update Main Application
- [x] Update `app/main.py`
  - [x] Remove old router imports
  - [x] Add new content and logs routers
  - [x] Update middleware if needed
  - [x] Ensure markdown filter is available for Jinja2

- [x] Update router implementations to use:
  - [x] Unified Content model from `app/models/schema.py`
  - [x] Domain converters from `app/domain/converters.py`
  - [x] Proper database session handling

## Phase 8: Update Styles
- [x] Review and update `static/css/styles.css`
  - [x] Remove any admin-specific styles
  - [x] Add mobile-first utility classes if needed
  - [x] Ensure good readability on small screens
  
- [x] Rebuild CSS with Tailwind CLI:
  ```bash
  npx @tailwindcss/cli -i ./static/css/styles.css -o ./static/css/app.css
  ```

## Phase 9: Testing and Cleanup
- [x] Remove tests for deleted components:
  - [x] Tests for old API endpoints
  - [x] Tests for admin functionality
  - [x] Tests for old routers

- [x] Test new UI:
  - [x] Content list with filters
  - [x] Content detail pages
  - [x] Admin logs viewer
  - [x] Mobile responsiveness

## Implementation Notes

### Database Query Patterns
- Use the unified Content model: `from app.models.schema import Content`
- Filter by content_type: `Content.content_type == ContentType.ARTICLE.value`
- Filter by date: Use `Content.created_at` or `processed_at`
- Join is no longer needed since Content has all data

### Template Context Variables
- List view: `contents`, `content_types`, `selected_date`, `selected_type`
- Detail view: `content`, with metadata accessed via `content.content_metadata`
- Use `content_to_domain()` converter when needed

### Mobile Optimization
- Use Tailwind's responsive prefixes: `sm:`, `md:`, `lg:`
- Test on actual mobile devices or responsive mode
- Ensure touch targets are at least 44x44 pixels
- Use appropriate font sizes (min 16px for body text)

### Error Handling
- Handle missing content gracefully with 404 pages
- Show user-friendly messages for empty states
- Log errors appropriately using the error logger

## Dependencies
- All existing dependencies should work
- No new packages needed
- Ensure TailwindCSS CLI is available for rebuilding styles