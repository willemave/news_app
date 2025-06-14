# News Aggregation App - Task List

## Overview

This document tracks development tasks for the unified news aggregation system. The project has recently undergone major architectural changes:

1. **✅ COMPLETED: Model Unification** - Migrated from separate Article/Podcast models to unified Content model
2. **✅ COMPLETED: Queue System** - Replaced Huey with database-backed queue
3. **✅ COMPLETED: Error Logger** - Replaced RSS-specific logger with generic error logger
4. **✅ COMPLETED: File Rename** - Changed `app/models/unified.py` to `app/models/schema.py`

## Current Architecture Status

### ✅ Completed Migrations
- [x] **Unified Content Model**: Single [`Content`](app/models/schema.py:24) model for all content types
- [x] **Database Queue**: [`ProcessingTask`](app/models/schema.py:59) replaces Huey
- [x] **Generic Error Logger**: [`GenericErrorLogger`](app/utils/error_logger.py:29) with full context capture
- [x] **LLM Service Abstraction**: Provider-based architecture with OpenAI/Mock providers
- [x] **Strategy Pattern**: URL processing strategies for different content types

### 🚧 In Progress
- [ ] **Router Migration**: Update routers to use unified Content model
- [ ] **Template Updates**: Modify templates for unified content display
- [ ] **Test Suite Updates**: Update tests for new architecture

## Phase 1: Complete Router Migration

### Task 1.1: Update Article Router
- [ ] **Read Current Router**: Review [`app/routers/articles.py`](app/routers/articles.py)
- [ ] **Update Imports**: Change from old models to `app.models.schema`
- [ ] **Update Queries**: Use Content model with `content_type='article'` filter
- [ ] **Fix Joins**: Remove Links table joins (no longer needed)
- [ ] **Test Endpoints**: Verify all article endpoints work

### Task 1.2: Update Podcast Router  
- [ ] **Read Current Router**: Review [`app/routers/podcasts.py`](app/routers/podcasts.py)
- [ ] **Update Imports**: Change from old models to `app.models.schema`
- [ ] **Update Queries**: Use Content model with `content_type='podcast'` filter
- [ ] **Metadata Access**: Use `content_metadata` JSON field for podcast data
- [ ] **Test Endpoints**: Verify all podcast endpoints work

### Task 1.3: Update Admin Router
- [ ] **Read Current Router**: Review [`app/routers/admin.py`](app/routers/admin.py)
- [ ] **Update Dashboard**: Show unified content stats
- [ ] **Update Controls**: Adapt for new queue system
- [ ] **Pipeline Status**: Show ProcessingTask queue status

## Phase 2: Template Updates

### Task 2.1: Article Templates
- [ ] **Update Base Template**: Review [`templates/base.html`](templates/base.html)
- [ ] **Update Article List**: Modify [`templates/articles.html`](templates/articles.html)
- [ ] **Update Article Detail**: Modify [`templates/detailed_article.html`](templates/detailed_article.html)
- [ ] **Fix Data Access**: Use content_metadata for article fields

### Task 2.2: Podcast Templates
- [ ] **Update Podcast List**: Modify [`templates/podcasts.html`](templates/podcasts.html)
- [ ] **Update Podcast Detail**: Modify [`templates/podcast_detail.html`](templates/podcast_detail.html)
- [ ] **Transcript Display**: Access transcript from content_metadata

### Task 2.3: Admin Templates
- [ ] **Update Dashboard**: Modify [`templates/admin_dashboard.html`](templates/admin_dashboard.html)
- [ ] **Queue Display**: Show ProcessingTask queue status
- [ ] **Error Display**: Show generic error logger output

## Phase 3: Test Suite Updates

### Task 3.1: Model Tests
- [ ] **Update Fixtures**: Create fixtures for unified Content model
- [ ] **Update Imports**: Fix all test imports to use new models
- [ ] **Test Content Creation**: Verify both article and podcast creation

### Task 3.2: Pipeline Tests
- [ ] **Queue Tests**: Test new ProcessingTask queue
- [ ] **Worker Tests**: Update for ContentWorker
- [ ] **Integration Tests**: Full pipeline with new architecture

### Task 3.3: Scraper Tests
- [ ] **Update Mocks**: Mock unified Content model
- [ ] **Test Data Creation**: Verify scrapers create correct content
- [ ] **Error Logger Tests**: Test generic error logger integration

## Phase 4: Database Migration

### Task 4.1: Migration Script
- [ ] **Create Migration**: Script to migrate old data to new schema
- [ ] **Map Articles**: Convert Articles table to Content entries
- [ ] **Map Podcasts**: Convert Podcasts table to Content entries
- [ ] **Preserve Data**: Ensure no data loss during migration

### Task 4.2: Backup & Recovery
- [ ] **Backup Strategy**: Document backup process
- [ ] **Test Migration**: Run on test database first
- [ ] **Rollback Plan**: Create rollback procedure

## Phase 5: Documentation Updates

### Task 5.1: API Documentation
- [ ] **Update OpenAPI**: Reflect new content model
- [ ] **Document Endpoints**: Update endpoint documentation
- [ ] **Example Requests**: Provide new request/response examples

### Task 5.2: Architecture Docs
- [ ] **Update Pipeline Doc**: [`docs/pipeline_architecture.md`](docs/pipeline_architecture.md)
- [ ] **Update Podcast Flow**: [`docs/podcast_processing_flow.md`](docs/podcast_processing_flow.md)
- [ ] **Create Migration Guide**: Document migration process

## Phase 6: Enhancement Tasks

### Task 6.1: LLM Provider Expansion
- [ ] **Anthropic Provider**: Add Claude support
- [ ] **Local Model Provider**: Add llama.cpp or similar
- [ ] **Provider Selection**: Dynamic provider selection

### Task 6.2: Content Categorization
- [ ] **Category Model**: Add content categories
- [ ] **Auto-Categorization**: LLM-based categorization
- [ ] **UI Filtering**: Filter by category in UI

### Task 6.3: Performance Optimization
- [ ] **Database Indexes**: Optimize for common queries
- [ ] **Caching Layer**: Add Redis for frequently accessed content
- [ ] **Batch Processing**: Optimize batch operations

## Quick Reference

### Key Files Changed
- **Models**: [`app/models/schema.py`](app/models/schema.py) - Unified content model
- **Queue**: [`app/services/queue.py`](app/services/queue.py) - Database-backed queue
- **Workers**: [`app/pipeline/worker.py`](app/pipeline/worker.py) - Unified content worker
- **Error Logger**: [`app/utils/error_logger.py`](app/utils/error_logger.py) - Generic logger

### Migration Commands
```bash
# Run scrapers
python scripts/run_scrapers_unified.py

# Process content
python scripts/run_unified_pipeline.py

# Run tests
pytest app/tests/ -v

# Format code
ruff format .

# Lint code
ruff check .
```

### Environment Setup
```bash
# Install dependencies
uv sync

# Activate environment
source .venv/bin/activate

# Copy environment template
cp .env.example .env

# Initialize database
python scripts/init_database.py
```

## Notes & Learnings

### Architecture Decisions
- **Unified Model**: Simplifies codebase, reduces duplication
- **JSON Metadata**: Flexible storage for type-specific data
- **Database Queue**: Simpler than external queue, good for this scale
- **Generic Logger**: Better debugging across all components

### Challenges Encountered
- Router updates need careful query modifications
- Template access patterns changed with JSON metadata
- Test fixtures need complete rewrite
- Migration script critical for production deployment

### Next Session Priority
1. Complete router migrations (Phase 1)
2. Update templates (Phase 2) 
3. Create database migration script (Phase 4.1)

---

**Last Updated**: 2025-06-14
**Current Focus**: Router migration to unified Content model
**Blocking Issues**: None
**Dependencies to Add**: None currently