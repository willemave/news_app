from __future__ import annotations

import pytest

from app.services import exa_client


def test_exa_search_returns_empty_results_when_client_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(exa_client, "get_exa_client", lambda: None)

    assert exa_client.exa_search("ai agents") == []


def test_exa_get_contents_raises_when_strict_mode_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(exa_client, "get_exa_client", lambda: None)

    with pytest.raises(exa_client.ExaUnavailableError):
        exa_client.exa_get_contents(
            ["https://example.com/story"],
            raise_on_error=True,
        )
