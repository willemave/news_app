"""Tests for application middleware behaviour."""


def test_request_id_is_returned(client) -> None:
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["X-Request-ID"]


def test_request_id_is_propagated(client) -> None:
    response = client.get("/", headers={"X-Request-ID": "req-123"}, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["X-Request-ID"] == "req-123"
