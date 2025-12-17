"""Tests for logging module, including JSONL error handler and redaction."""

import json
import logging
from unittest.mock import MagicMock, patch

from app.core.logging import (
    _build_error_json_payload,
    _redact_value,
    _sanitize_filename,
)


class TestRedactValue:
    """Tests for sensitive data redaction."""

    def test_redacts_authorization_header(self):
        """Test that authorization headers are redacted."""
        headers = {"authorization": "Bearer secret-token-123"}
        result = _redact_value(headers)
        assert result["authorization"] == "<redacted>"

    def test_redacts_cookie_header(self):
        """Test that cookie headers are redacted."""
        headers = {"cookie": "session=abc123; user=test"}
        result = _redact_value(headers)
        assert result["cookie"] == "<redacted>"

    def test_redacts_api_key_variations(self):
        """Test that various API key field names are redacted."""
        data = {
            "api-key": "key123",
            "apikey": "key456",
            "x-api-key": "key789",
            "APIKEY": "key000",  # Case-insensitive matching
        }
        result = _redact_value(data)
        assert result["api-key"] == "<redacted>"
        assert result["apikey"] == "<redacted>"
        assert result["x-api-key"] == "<redacted>"
        assert result["APIKEY"] == "<redacted>"

    def test_redacts_token_fields(self):
        """Test that token fields are redacted."""
        data = {
            "token": "tok123",
            "access_token": "access123",
            "refresh_token": "refresh123",
        }
        result = _redact_value(data)
        assert result["token"] == "<redacted>"
        assert result["access_token"] == "<redacted>"
        assert result["refresh_token"] == "<redacted>"

    def test_redacts_password_and_secret(self):
        """Test that password and secret fields are redacted."""
        data = {"password": "secret123", "secret": "mysecret", "jwt_secret_key": "jwtsec"}
        result = _redact_value(data)
        assert result["password"] == "<redacted>"
        assert result["secret"] == "<redacted>"
        assert result["jwt_secret_key"] == "<redacted>"

    def test_redacts_bearer_token_in_string(self):
        """Test that Bearer tokens in strings are redacted."""
        value = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        result = _redact_value(value)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result
        assert "Bearer <redacted>" in result

    def test_redacts_nested_dicts(self):
        """Test that nested dictionaries are redacted recursively."""
        data = {
            "outer": {"inner": {"password": "secret123", "safe_field": "visible"}},
            "normal_field": "also_visible",
        }
        result = _redact_value(data)
        assert result["outer"]["inner"]["password"] == "<redacted>"
        assert result["outer"]["inner"]["safe_field"] == "visible"
        assert result["normal_field"] == "also_visible"

    def test_redacts_values_in_lists(self):
        """Test that values in lists are redacted recursively."""
        data = [{"password": "secret"}, {"username": "visible"}]
        result = _redact_value(data)
        assert result[0]["password"] == "<redacted>"
        assert result[1]["username"] == "visible"

    def test_redacts_values_in_tuples(self):
        """Test that values in tuples are redacted recursively."""
        data = ({"token": "secret"}, {"data": "visible"})
        result = _redact_value(data)
        assert result[0]["token"] == "<redacted>"
        assert result[1]["data"] == "visible"
        assert isinstance(result, tuple)

    def test_preserves_non_sensitive_data(self):
        """Test that non-sensitive data is preserved."""
        data = {"username": "testuser", "email": "test@example.com", "count": 42}
        result = _redact_value(data)
        assert result == data

    def test_handles_none_values(self):
        """Test that None values pass through unchanged."""
        assert _redact_value(None) is None

    def test_handles_numeric_values(self):
        """Test that numeric values pass through unchanged."""
        assert _redact_value(42) == 42
        assert _redact_value(3.14) == 3.14


class TestSanitizeFilename:
    """Tests for filename sanitization."""

    def test_sanitizes_special_characters(self):
        """Test that special characters are replaced with underscores."""
        assert _sanitize_filename("my/log:file") == "my_log_file"
        assert _sanitize_filename("test@component") == "test_component"

    def test_converts_to_lowercase(self):
        """Test that filenames are converted to lowercase."""
        assert _sanitize_filename("MyLogFile") == "mylogfile"

    def test_strips_leading_trailing_chars(self):
        """Test that leading/trailing special chars are stripped."""
        assert _sanitize_filename("_test_") == "test"
        assert _sanitize_filename("...test...") == "test"

    def test_returns_app_for_empty(self):
        """Test that empty strings return 'app'."""
        assert _sanitize_filename("") == "app"
        assert _sanitize_filename("   ") == "app"


class TestBuildErrorJsonPayload:
    """Tests for building JSON error payloads from log records."""

    def test_basic_error_payload(self):
        """Test basic error payload construction."""
        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test_file.py",
            lineno=42,
            msg="Test error message",
            args=(),
            exc_info=None,
        )

        payload = _build_error_json_payload(record)

        assert payload["level"] == "ERROR"
        assert payload["logger"] == "test.logger"
        assert payload["message"] == "Test error message"
        assert payload["source_file"] == "test_file.py"
        assert payload["source_line"] == 42
        assert "timestamp" in payload

    def test_payload_with_exception_info(self):
        """Test payload includes exception info when available."""
        try:
            raise ValueError("Test exception")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test_file.py",
            lineno=42,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )

        payload = _build_error_json_payload(record)

        assert payload["error_type"] == "ValueError"
        assert payload["error_message"] == "Test exception"
        assert "stack_trace" in payload
        assert "ValueError: Test exception" in payload["stack_trace"]

    def test_payload_with_extra_fields(self):
        """Test payload includes extra fields from log record."""
        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test_file.py",
            lineno=42,
            msg="Processing error",
            args=(),
            exc_info=None,
        )
        record.component = "content_worker"
        record.operation = "summarize"
        record.item_id = 123
        record.context_data = {"url": "https://example.com"}
        record.http_details = {"status_code": 500}

        payload = _build_error_json_payload(record)

        assert payload["component"] == "content_worker"
        assert payload["operation"] == "summarize"
        assert payload["item_id"] == 123
        assert payload["context_data"] == {"url": "https://example.com"}
        assert payload["http_details"] == {"status_code": 500}

    def test_payload_redacts_sensitive_context(self):
        """Test that sensitive data in context is redacted."""
        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test_file.py",
            lineno=42,
            msg="Auth error",
            args=(),
            exc_info=None,
        )
        record.context_data = {"password": "secret123", "username": "testuser"}
        record.http_details = {"headers": {"authorization": "Bearer token123"}}

        payload = _build_error_json_payload(record)

        assert payload["context_data"]["password"] == "<redacted>"
        assert payload["context_data"]["username"] == "testuser"
        assert payload["http_details"]["headers"]["authorization"] == "<redacted>"

    def test_payload_uses_component_for_component_field(self):
        """Test that component field uses explicit component if set."""
        record = logging.LogRecord(
            name="error.worker",
            level=logging.ERROR,
            pathname="test_file.py",
            lineno=42,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.component = "custom_component"

        payload = _build_error_json_payload(record)

        assert payload["component"] == "custom_component"

    def test_payload_falls_back_to_logger_name(self):
        """Test that component falls back to logger name if not set."""
        record = logging.LogRecord(
            name="error.worker",
            level=logging.ERROR,
            pathname="test_file.py",
            lineno=42,
            msg="Test",
            args=(),
            exc_info=None,
        )

        payload = _build_error_json_payload(record)

        assert payload["component"] == "error.worker"

    def test_payload_omits_none_values(self):
        """Test that None values are omitted from payload."""
        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test_file.py",
            lineno=42,
            msg="Test",
            args=(),
            exc_info=None,
        )

        payload = _build_error_json_payload(record)

        # These should not be present since they're None
        assert "context_data" not in payload
        assert "http_details" not in payload
        assert "item_id" not in payload
        assert "operation" not in payload


class TestJsonLineErrorFormatter:
    """Tests for JSONL error formatter."""

    def test_formats_as_valid_json(self):
        """Test that formatter produces valid JSON."""
        from app.core.logging import _JsonLineErrorFormatter

        formatter = _JsonLineErrorFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)

        # Should be valid JSON
        parsed = json.loads(result)
        assert parsed["message"] == "Test message"
        assert parsed["level"] == "ERROR"

    def test_handles_unicode_content(self):
        """Test that formatter handles unicode content."""
        from app.core.logging import _JsonLineErrorFormatter

        formatter = _JsonLineErrorFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Error with unicode: \u00e9\u00e8\u00ea \u4e2d\u6587",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        parsed = json.loads(result)

        assert "\u00e9\u00e8\u00ea" in parsed["message"]
        assert "\u4e2d\u6587" in parsed["message"]
