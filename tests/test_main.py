"""Tests for application middleware behaviour."""

from pathlib import Path

import app.main as main_module


def test_request_id_is_returned(client) -> None:
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["X-Request-ID"]


def test_request_id_is_propagated(client) -> None:
    response = client.get("/", headers={"X-Request-ID": "req-123"}, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["X-Request-ID"] == "req-123"


def test_static_mount_directories_are_created(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(main_module.settings, "images_base_dir", tmp_path / "data" / "images")

    images_dir, static_dir = main_module._ensure_static_mount_directories()

    assert images_dir == (tmp_path / "data" / "images").resolve()
    assert static_dir == (tmp_path / "static").resolve()
    assert images_dir.is_dir()
    assert static_dir.is_dir()
