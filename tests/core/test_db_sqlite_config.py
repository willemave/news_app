"""Tests for SQLite database engine configuration."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import text

import app.core.db as core_db


def test_init_db_configures_sqlite_pragmas(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "sqlite-config.db"
    settings = SimpleNamespace(
        database_url=f"sqlite:///{db_path}",
        database_pool_size=20,
        database_max_overflow=40,
        debug=False,
    )

    monkeypatch.setattr(core_db, "get_settings", lambda: settings)
    monkeypatch.setattr(core_db, "_engine", None)
    monkeypatch.setattr(core_db, "_SessionLocal", None)

    try:
        core_db.init_db()
        engine = core_db.get_engine()
        with engine.connect() as conn:
            journal_mode = conn.execute(text("PRAGMA journal_mode")).scalar()
            busy_timeout = conn.execute(text("PRAGMA busy_timeout")).scalar()
            foreign_keys = conn.execute(text("PRAGMA foreign_keys")).scalar()

        assert str(journal_mode).lower() == "wal"
        assert int(busy_timeout) == 30000
        assert int(foreign_keys) == 1
    finally:
        if core_db._engine is not None:
            core_db._engine.dispose()
        monkeypatch.setattr(core_db, "_engine", None)
        monkeypatch.setattr(core_db, "_SessionLocal", None)
