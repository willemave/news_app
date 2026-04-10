"""Tests for admin.remote runtime context resolution."""

from __future__ import annotations

from admin.remote import _resolve_runtime_database_url


def test_resolve_runtime_database_url_keeps_real_url(monkeypatch):
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret")

    resolved = _resolve_runtime_database_url(
        "postgresql+psycopg://newsly:real@127.0.0.1:5432/newsly"
    )

    assert resolved == "postgresql+psycopg://newsly:real@127.0.0.1:5432/newsly"


def test_resolve_runtime_database_url_rebuilds_placeholder_url(monkeypatch):
    monkeypatch.setenv("POSTGRES_USER", "newsly")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret")
    monkeypatch.setenv("POSTGRES_DB", "newsly")
    monkeypatch.setenv("POSTGRES_PORT", "5432")

    resolved = _resolve_runtime_database_url(
        "postgresql+psycopg://newsly:change-me@127.0.0.1:5432/newsly"
    )

    assert resolved == "postgresql+psycopg://newsly:secret@127.0.0.1:5432/newsly"
