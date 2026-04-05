"""Tests for agent CLI QR-linking endpoints."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse


def test_agent_cli_link_flow_issues_api_key_once(
    client_factory,
    test_user,
) -> None:
    """CLI link sessions should approve once and reveal the API key once."""
    with client_factory(authenticate=False) as anonymous_client:
        start_response = anonymous_client.post("/api/agent/cli/link/start")

    assert start_response.status_code == 200
    start_payload = start_response.json()
    assert start_payload["status"] == "pending"
    assert start_payload["session_id"]
    assert start_payload["poll_token"]
    assert start_payload["approve_url"].startswith("newsly://cli-link?")

    approve_url = urlparse(start_payload["approve_url"])
    approve_params = parse_qs(approve_url.query)
    session_id = approve_params["session_id"][0]
    approve_token = approve_params["approve_token"][0]

    with client_factory(user=test_user) as authenticated_client:
        approve_response = authenticated_client.post(
            f"/api/agent/cli/link/{session_id}/approve",
            json={"approve_token": approve_token, "device_name": "MacBook Pro"},
        )

    assert approve_response.status_code == 200
    approve_payload = approve_response.json()
    assert approve_payload["session_id"] == session_id
    assert approve_payload["status"] == "approved"
    assert approve_payload["key_prefix"].startswith("newsly_ak_")

    with client_factory(authenticate=False) as anonymous_client:
        poll_response = anonymous_client.get(
            f"/api/agent/cli/link/{session_id}",
            params={"poll_token": start_payload["poll_token"]},
        )

    assert poll_response.status_code == 200
    poll_payload = poll_response.json()
    assert poll_payload["session_id"] == session_id
    assert poll_payload["status"] == "approved"
    assert poll_payload["api_key"].startswith("newsly_ak_")
    assert poll_payload["key_prefix"] == approve_payload["key_prefix"]

    with client_factory(authenticate=False) as anonymous_client:
        second_poll_response = anonymous_client.get(
            f"/api/agent/cli/link/{session_id}",
            params={"poll_token": start_payload["poll_token"]},
        )

    assert second_poll_response.status_code == 200
    second_poll_payload = second_poll_response.json()
    assert second_poll_payload["session_id"] == session_id
    assert second_poll_payload["status"] == "claimed"
    assert second_poll_payload["api_key"] is None


def test_agent_cli_link_approve_rejects_invalid_token(
    client_factory,
    test_user,
) -> None:
    """Approval should reject mismatched approve tokens."""
    with client_factory(authenticate=False) as anonymous_client:
        start_response = anonymous_client.post("/api/agent/cli/link/start")

    session_id = start_response.json()["session_id"]
    with client_factory(user=test_user) as authenticated_client:
        response = authenticated_client.post(
            f"/api/agent/cli/link/{session_id}/approve",
            json={"approve_token": "wrong-token"},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid CLI link approval token"
