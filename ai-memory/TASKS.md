# News App Development Tasks

## Phase: Links Table Implementation

### Database & Models
- [x] Create LinkStatus enum in models.py
- [x] Create Links model with all required fields
- [x] Update Articles model - remove raw_content and status columns
- [x] Add bidirectional relationship between Links and Articles
- [x] Create Pydantic schemas for Links (LinkBase, LinkCreate, Link)
- [x] Update Article schemas - remove raw_content and status fields

### Processor Updates
- [x] Modify process_single_link to accept Link object
- [x] Update link status to "processing" at start
- [x] Remove raw_content storage in create_article_and_summary
- [x] Link created Article to Link record
- [x] Update link status to "processed" or "failed" based on outcome
- [x] Store error messages in Link record on failure

### Queue Updates  
- [x] Change process_link_task to accept link_id parameter
- [x] Fetch Link from database by ID
- [x] Pass Link object to processor
- [x] Handle Link not found errors

### Scraper Updates
- [x] Update HackerNews scraper to create Link records
- [x] Update Reddit scraper to create Link records
- [x] Replace process_link_task calls with link_id based calls
- [x] Add duplicate URL checking at Link creation

### Migration
- [x] Create migration script for existing data
- [ ] Test migration on backup database
- [ ] Document rollback procedure

### Testing & Validation
- [ ] Test end-to-end flow with new Links table
- [ ] Verify no data loss during migration
- [ ] Update any affected API endpoints
- [ ] Update admin dashboard if needed

## Key Files Updated
- [x] app/models.py (Links model, update Articles)
- [x] app/schemas.py (Link schemas, update Article schemas)
- [x] app/processor.py (modify processing logic)
- [x] app/queue.py (update task parameters)
- [x] app/scraping/hackernews_scraper.py (create Links instead of direct queue)
- [x] app/scraping/reddit.py (create Links instead of direct queue)
- [x] scripts/migrate_to_links_table.py (migration script)

## Architecture Changes
- **Before**: Scrapers → Queue → Process → Articles (with raw_content, status)
- **After**: Scrapers → Links table → Queue → Process → Articles (clean) + Update Links status

## Implementation Summary

### What's Been Implemented:
1. **New Links Table**: Stores all scraped URLs with status tracking
2. **Updated Articles Table**: Removed raw_content and status, added link_id foreign key
3. **Enhanced Processor**: Now works with Link objects, updates link status during processing
4. **Updated Queue System**: Tasks now reference link_id instead of passing URLs
5. **Modified Scrapers**: Create Link records before queuing for processing
6. **Migration Script**: Complete migration from old to new architecture

### Key Benefits:
- **Separation of Concerns**: Link discovery separate from content processing
- **Better Status Tracking**: Can track link processing independent of article creation
- **Cleaner Data Model**: Articles only contain processed content, not raw data
- **Improved Error Handling**: Link-level error tracking and retry capability
- **Duplicate Prevention**: URL deduplication at the link level

### Next Steps:
1. Run migration script on existing database
2. Test the new flow end-to-end
3. Update any API endpoints that reference old Article fields
4. Update admin dashboard to show Links table information
