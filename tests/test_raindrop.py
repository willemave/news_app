import pytest
import datetime
from unittest.mock import patch
from app.scraping.raindrop import fetch_new_raindrops
from app.config import settings

@pytest.fixture
def mock_settings():
    """Mock settings to provide a test token"""
    with patch('app.config.settings.RAINDROP_TOKEN', 'test-token'):
        yield

def test_fetch_new_raindrops_no_token():
    """Test that the function returns empty list when no token is configured"""
    with patch('app.config.settings.RAINDROP_TOKEN', ''):
        result = fetch_new_raindrops(datetime.datetime.utcnow())
        assert result == []

def test_fetch_new_raindrops_success(mock_settings):
    """Test successful fetching of raindrops"""
    last_run_date = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
    mock_response = {
        "items": [
            {
                "link": "https://example.com/article1",
                "title": "Test Article 1",
                "created": "2024-01-02T10:00:00Z"
            },
            {
                "link": "https://example.com/article2",
                "title": "Test Article 2",
                "created": "2024-01-02T11:00:00Z"
            }
        ]
    }
    
    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_response
        result = fetch_new_raindrops(last_run_date)
        
        assert len(result) == 2
        assert result[0]["url"] == "https://example.com/article1"
        assert result[1]["url"] == "https://example.com/article2"

def test_fetch_new_raindrops_api_error(mock_settings):
    """Test handling of API errors"""
    last_run_date = datetime.datetime.now(datetime.timezone.utc)
    
    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 500
        result = fetch_new_raindrops(last_run_date)
        assert result == [] 
