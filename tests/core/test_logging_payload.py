"""Tests for error payload and JSON line formatter behavior."""

import json
import logging

from app.core.logging import _build_error_json_payload


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

    def test_payload_merges_unstructured_extras(self):
        """Test payload merges extra fields into context_data."""
        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test_file.py",
            lineno=42,
            msg="Processing error",
            args=(),
            exc_info=None,
        )
        record.user_id = 999
        record.context_data = {"content_id": 123}

        payload = _build_error_json_payload(record)

        assert payload["context_data"]["content_id"] == 123
        assert payload["context_data"]["user_id"] == 999

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
