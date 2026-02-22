# Test Fixtures Usage Guide

This guide demonstrates how to use the test fixtures in your processing pipeline tests.

## Quick Start

The fixtures are automatically available in all tests through pytest's conftest.py. Just add them as function parameters:

```python
def test_something(sample_article_long):
    # Use the fixture
    assert sample_article_long["content_type"] == "article"
```

## Available Fixtures

### Completed Content (for validation tests)

**`sample_article_long`** - Long-form technical article (Mini NAS review)
- Full HTML content scraped from web
- Complete structured summary with 4+ bullet points
- Multiple quotes
- Topics and classification
- Use for: Testing summary structure validation, rendering, display

**`sample_article_short`** - Short technical article (Rust QR code)
- Concise technical content
- Shorter summary (fewer bullet points)
- Use for: Testing different content lengths, technical content processing

**`sample_podcast`** - Podcast episode (OpenAI interview)
- Complete audio metadata (URL, duration, file paths)
- Full transcript
- Complete structured summary
- Use for: Testing podcast-specific features, transcript handling

### Unprocessed Content (for pipeline tests)

**`sample_unprocessed_article`** - Article ready for processing
- Raw HTML content
- Status: `new`
- No summary yet
- Use for: Testing scraping → summarization pipeline

**`sample_unprocessed_podcast`** - Podcast with transcript
- Has transcript already
- Status: `processing`
- No summary yet
- Use for: Testing transcript → summarization step

## Common Usage Patterns

### 1. Validating Fixture Structure

```python
def test_article_structure(sample_article_long):
    """Verify fixture has expected fields."""
    assert "content_metadata" in sample_article_long
    assert "summary" in sample_article_long["content_metadata"]

    summary = sample_article_long["content_metadata"]["summary"]
    assert "title" in summary
    assert "bullet_points" in summary
    assert len(summary["bullet_points"]) >= 3
```

### 2. Creating Database Records from Fixtures

```python
def test_with_db_content(create_sample_content, sample_article_long, db_session):
    """Create content in database from fixture."""
    # Create content
    content = create_sample_content(sample_article_long)

    # Verify it's in the database
    assert content.id is not None
    assert content.status == "completed"

    # Query it back
    db_content = db_session.query(Content).filter_by(id=content.id).first()
    assert db_content is not None
```

### 3. Testing Processing Pipeline

```python
from conftest import create_content_from_fixture

def test_process_unprocessed_article(sample_unprocessed_article, db_session):
    """Test processing an unprocessed article."""
    # Create unprocessed content in DB
    content = create_content_from_fixture(sample_unprocessed_article)
    db_session.add(content)
    db_session.commit()

    # Process it (with mocked LLM)
    worker = ContentWorker()
    with patch("app.pipeline.worker.get_llm_service") as mock_llm:
        mock_llm.return_value.summarize_content.return_value = mock_summary
        result = worker.process_content(content.id, "test-worker")

    # Verify it was processed
    db_session.refresh(content)
    assert content.status == "completed"
    assert "summary" in content.content_metadata
```

### 4. Parameterized Tests with Multiple Fixtures

```python
@pytest.mark.parametrize(
    "fixture_name,expected_type",
    [
        ("sample_article_long", "article"),
        ("sample_article_short", "article"),
        ("sample_podcast", "podcast"),
    ],
)
def test_content_types(fixture_name, expected_type, request):
    """Test all fixtures have correct content type."""
    fixture_data = request.getfixturevalue(fixture_name)
    assert fixture_data["content_type"] == expected_type
```

### 5. Testing Different Processing Stages

```python
def test_scraping_stage(sample_unprocessed_article):
    """Test content at scraping stage."""
    # This fixture has raw content but no summary
    assert "content" in sample_unprocessed_article["content_metadata"]
    assert "summary" not in sample_unprocessed_article["content_metadata"]

def test_summarization_stage(sample_article_long):
    """Test content at completed stage."""
    # This fixture has both content and summary
    assert "content" in sample_article_long["content_metadata"]
    assert "summary" in sample_article_long["content_metadata"]
```

## Integration Test Examples

### Complete Pipeline Test

```python
@pytest.mark.integration
def test_full_pipeline_with_fixtures(
    db_session,
    sample_unprocessed_article,
    create_sample_content
):
    """Test complete flow from raw content to summary."""
    # Setup: Create unprocessed content
    content = create_sample_content(sample_unprocessed_article)
    assert content.status == "new"

    # Mock external services
    with (
        patch("app.pipeline.worker.get_strategy_registry") as mock_registry,
        patch("app.pipeline.worker.get_llm_service") as mock_llm,
    ):
        # Setup mocks to use fixture content
        mock_strategy = Mock()
        mock_strategy.extract_data.return_value = {
            "text_content": sample_unprocessed_article["content_metadata"]["content"],
            "content_type": "html",
        }
        mock_registry.return_value.get_strategy.return_value = mock_strategy

        mock_llm.return_value.summarize_content.return_value = create_test_summary()

        # Execute: Process the content
        worker = ContentWorker()
        result = worker.process_content(content.id, "test-worker")

    # Verify: Content was processed successfully
    assert result is True
    db_session.refresh(content)
    assert content.status == "completed"
    assert "summary" in content.content_metadata
```

## Tips

1. **Use unprocessed fixtures** for testing the processing pipeline
2. **Use completed fixtures** for testing rendering, validation, and display logic
3. **Create DB records** when you need to test database interactions
4. **Use fixture data directly** when testing pure functions or validation logic
5. **Mock LLM responses** to avoid API calls and ensure deterministic tests

## Fixture Data Location

All fixture data is in: `tests/fixtures/content_samples.json`

This JSON file contains the raw data. The pytest fixtures in `conftest.py` load and provide this data to your tests.

## Adding New Fixtures

To add a new fixture:

1. Query your database for a good example
2. Extract the full record including metadata
3. Add it to `content_samples.json`
4. Add a pytest fixture in `conftest.py`:
   ```python
   @pytest.fixture
   def sample_my_new_fixture(content_samples):
       return content_samples["my_new_fixture_key"]
   ```
5. Update the documentation in `README.md`

## Real Examples

See these files for complete working examples:
- `tests/test_fixtures_example.py` - Basic fixture usage
- `tests/pipeline/test_worker_with_fixtures.py` - Worker tests with fixtures
- `tests/integration/test_pipeline_with_fixtures.py` - Integration tests

## Benefits

✅ **Realistic data** - Real examples from your production database
✅ **Consistent tests** - Everyone uses the same test data
✅ **Fast tests** - No need to scrape/process during tests
✅ **Comprehensive** - Covers all processing stages
✅ **Easy to use** - Just add as function parameter
