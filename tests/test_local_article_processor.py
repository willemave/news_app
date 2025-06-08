import pytest
from unittest.mock import patch, MagicMock, mock_open

from app.models import Articles, ArticleStatus
from app.schemas import ArticleSummary
from scripts.process_local_articles import process_new_local_articles

# Mock Article object
mock_article = Articles()
mock_article.id=1
mock_article.title="Test Article"
mock_article.local_path="data/test/test-article.md"
mock_article.status=ArticleStatus.new

@pytest.fixture
def mock_db_session():
    """Fixture for a mocked database session."""
    mock_session = MagicMock()
    # Simulate finding one article to process
    mock_session.query.return_value.filter.return_value.all.return_value = [mock_article]
    return mock_session

@patch('scripts.process_local_articles.summarize_article')
def test_process_new_local_articles_success(mock_summarize_article, mock_db_session):
    """Test the successful processing of a new local article."""
    # Mock the summary result from the LLM
    mock_summary = ArticleSummary(
        short_summary="Short summary.",
        detailed_summary="Detailed summary."
    )
    mock_summarize_article.return_value = mock_summary

    # Mock file reading
    mock_html_content = "<html><body><h1>Title</h1><p>Article content.</p></body></html>"
    with patch('builtins.open', mock_open(read_data=mock_html_content)) as mock_file:
        # Run the processor
        process_new_local_articles(mock_db_session)

        # Assertions
        # 1. Check that the file was opened
        mock_file.assert_called_once_with("data/test/test-article.md", 'r', encoding='utf-8')

        # 2. Check that summarize_article was called with extracted content
        # Using trafilatura on the mock_html_content would yield "Title\nArticle content."
        mock_summarize_article.assert_called_once_with("Title\nArticle content.")

        # 3. Verify the article's status and summaries were updated
        assert mock_article.status == ArticleStatus.processed
        assert mock_article.short_summary == "Short summary."
        assert mock_article.detailed_summary == "Detailed summary."

        # 4. Check that the changes were committed
        mock_db_session.commit.assert_called_once()

def test_process_new_local_articles_file_not_found(mock_db_session):
    """Test handling of a FileNotFoundError."""
    # Mock file reading to raise an error
    with patch('builtins.open', side_effect=FileNotFoundError) as mock_file:
        # Run the processor
        process_new_local_articles(mock_db_session)

        # Assertions
        # 1. Check that the file open was attempted
        mock_file.assert_called_once_with("data/test/test-article.md", 'r', encoding='utf-8')

        # 2. Verify the article's status is updated to failed
        assert mock_article.status == ArticleStatus.failed

        # 3. Check that the changes were committed
        mock_db_session.commit.assert_called_once()

@patch('scripts.process_local_articles.summarize_article')
def test_process_new_local_articles_summarization_fails(mock_summarize_article, mock_db_session):
    """Test handling of a failure during LLM summarization."""
    # Mock the summary result to be None
    mock_summarize_article.return_value = None

    mock_html_content = "<html><body><p>Content</p></body></html>"
    with patch('builtins.open', mock_open(read_data=mock_html_content)):
        # Run the processor
        process_new_local_articles(mock_db_session)

        # Assertions
        # 1. Verify the article's status is updated to failed
        assert mock_article.status == ArticleStatus.failed

        # 2. Check that the changes were committed
        mock_db_session.commit.assert_called_once()