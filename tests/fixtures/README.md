# Test Fixtures

This directory contains test fixtures for the news app, extracted from real database entries. These fixtures provide representative examples of content at different stages of processing.

## Available Fixtures

### `content_samples.json`

Contains sample content in various states:

1. **article_long_form**: Long-form article with complete processing
   - Fully scraped HTML content
   - Complete structured summary with bullet points, quotes, topics
   - From HackerNews source
   - Status: completed

2. **article_short_technical**: Short technical article
   - Technical content (Linux kernel/Rust)
   - Concise summary
   - From HackerNews source
   - Status: completed

3. **podcast_interview**: Podcast episode with full processing
   - Complete transcript from audio file
   - Full structured summary
   - Includes metadata (duration, file paths, etc.)
   - Status: completed

4. **raw_content_unprocessed**: Unprocessed article
   - Raw scraped content
   - No summary yet
   - Status: new
   - Useful for testing the processing pipeline

5. **podcast_raw_transcript**: Podcast with transcript only
   - Transcript available
   - No summary yet
   - Status: processing
   - Useful for testing summarization step

## Usage in Tests

### Loading Fixture Data

```python
def test_with_fixture(sample_article_long):
    """Use a fixture directly as a dictionary."""
    assert sample_article_long["content_type"] == "article"
    assert "summary" in sample_article_long["content_metadata"]
```

### Creating Database Records

```python
def test_with_db_content(create_sample_content, sample_article_long):
    """Create a database record from fixture."""
    content = create_sample_content(sample_article_long)
    assert content.id is not None
    assert content.status == "completed"
```

### Testing Processing Pipeline

```python
def test_processing_pipeline(create_sample_content, sample_unprocessed_article):
    """Test content processing from raw to summarized."""
    # Create unprocessed content in DB
    content = create_sample_content(sample_unprocessed_article)

    # Run processing
    process_content(content)

    # Verify results
    assert content.status == "completed"
    assert "summary" in content.content_metadata
```

### Testing Different Content Types

```python
def test_article_processing(sample_article_long, sample_article_short):
    """Test with different article types."""
    long_summary = sample_article_long["content_metadata"]["summary"]
    short_summary = sample_article_short["content_metadata"]["summary"]

    assert len(long_summary["bullet_points"]) > len(short_summary["bullet_points"])

def test_podcast_processing(sample_podcast, sample_unprocessed_podcast):
    """Test podcast-specific processing."""
    completed = sample_podcast["content_metadata"]
    raw = sample_unprocessed_podcast["content_metadata"]

    assert "transcript" in completed
    assert "transcript" in raw
    assert "summary" in completed
    assert "summary" not in raw
```

## Fixture Structure

All fixtures follow the database schema structure:

```json
{
  "id": 1,
  "content_type": "article|podcast",
  "url": "https://...",
  "title": "...",
  "source": "...",
  "status": "new|pending|processing|completed|failed|skipped",
  "platform": "web|podcast",
  "classification": "to_read|...",
  "publication_date": "ISO 8601 date",
  "content_metadata": {
    "source": "...",
    "content": "raw content text...",
    "transcript": "for podcasts...",
    "summary": {
      "title": "...",
      "overview": "...",
      "bullet_points": [...],
      "quotes": [...],
      "topics": [...],
      "classification": "..."
    },
    // ... additional metadata
  }
}
```

## Adding New Fixtures

To add new fixtures:

1. Query the database for representative examples
2. Extract both raw content and processed summaries
3. Add to `content_samples.json` with a descriptive key
4. Add a corresponding pytest fixture in `conftest.py`
5. Update this README

## Benefits

- **Consistent test data**: All tests use the same representative samples
- **Real-world examples**: Data extracted from actual production database
- **Fast tests**: No need to scrape/process content during tests
- **Isolation**: Tests don't depend on external services
- **Coverage**: Examples at each stage of the processing pipeline
