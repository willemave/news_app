"""Tests for observability helper utilities."""

from app.core.observability import sanitize_url_for_logs, summarize_request_payload


def test_sanitize_url_for_logs_removes_query_values() -> None:
    result = sanitize_url_for_logs("https://example.com/path?a=1&token=secret")

    assert result is not None
    assert result["host"] == "example.com"
    assert result["path"] == "/path"
    assert result["query_keys"] == ["a", "token"]
    assert "secret" not in result["sanitized"]


def test_summarize_request_payload_json_only_tracks_shape() -> None:
    summary = summarize_request_payload(
        b'{"prompt":"x","article_text":"long text","count":2}',
        "application/json",
    )

    assert summary["shape"] == "json_object"
    assert summary["top_level_key_count"] == 3
    assert summary["top_level_keys"] == ["article_text", "count", "prompt"]


def test_summarize_request_payload_form_only_tracks_fields() -> None:
    summary = summarize_request_payload(
        b"email=test%40example.com&password=secret",
        "application/x-www-form-urlencoded",
    )

    assert summary["shape"] == "form"
    assert summary["field_names"] == ["email", "password"]
