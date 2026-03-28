"""Tests for request logging middleware behavior."""

import logging

from fastapi.testclient import TestClient

from app.main import app


def test_request_logging_propagates_request_id(caplog) -> None:
    """Middleware should echo inbound request IDs and emit structured metadata."""
    with TestClient(app) as client, caplog.at_level(logging.INFO):
        response = client.get("/", headers={"X-Request-ID": "req-test-123"})

    assert response.headers["X-Request-ID"] == "req-test-123"
    matching = [
        record
        for record in caplog.records
        if getattr(record, "event_name", None) == "http.request"
        and getattr(record, "status", None) == "completed"
    ]
    assert matching
    assert getattr(matching[-1], "request_id", None) == "req-test-123"
