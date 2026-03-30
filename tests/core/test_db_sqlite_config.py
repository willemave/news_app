"""Tests for SQLite database engine configuration and retry behavior."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

import app.core.db as core_db


def _build_settings(
    db_path: Path,
    *,
    sqlite_enable_wal: bool = False,
    sqlite_busy_timeout_ms: int = 30_000,
    sqlite_write_retry_attempts: int = 3,
) -> SimpleNamespace:
    return SimpleNamespace(
        database_url=f"sqlite:///{db_path}",
        database_pool_size=20,
        database_max_overflow=40,
        debug=False,
        sqlite_busy_timeout_ms=sqlite_busy_timeout_ms,
        sqlite_enable_wal=sqlite_enable_wal,
        sqlite_write_retry_attempts=sqlite_write_retry_attempts,
    )


def _reset_db_globals(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(core_db, "_engine", None)
    monkeypatch.setattr(core_db, "_SessionLocal", None)
    monkeypatch.setattr(core_db, "_sqlite_runtime_diagnostics_logged", False)


def test_init_db_preserves_existing_journal_mode_when_wal_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    db_path = tmp_path / "sqlite-config.db"
    existing_conn = sqlite3.connect(db_path)
    try:
        existing_conn.execute("PRAGMA journal_mode=WAL")
    finally:
        existing_conn.close()

    monkeypatch.setattr(core_db, "get_settings", lambda: _build_settings(db_path))
    _reset_db_globals(monkeypatch)
    caplog.set_level("INFO")

    try:
        core_db.init_db()
        engine = core_db.get_engine()
        with engine.connect() as conn:
            first_journal_mode = conn.execute(text("PRAGMA journal_mode")).scalar()
            busy_timeout = conn.execute(text("PRAGMA busy_timeout")).scalar()
            foreign_keys = conn.execute(text("PRAGMA foreign_keys")).scalar()
        with engine.connect() as conn:
            second_journal_mode = conn.execute(text("PRAGMA journal_mode")).scalar()

        assert str(first_journal_mode).lower() == "wal"
        assert str(second_journal_mode).lower() == "wal"
        assert int(busy_timeout) == 30000
        assert int(foreign_keys) == 1
        assert caplog.messages.count("SQLite runtime diagnostics") == 1
    finally:
        if core_db._engine is not None:
            core_db._engine.dispose()
        _reset_db_globals(monkeypatch)


def test_init_db_enables_wal_only_when_explicitly_enabled_and_runtime_safe(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "sqlite-wal.db"
    monkeypatch.setattr(
        core_db,
        "get_settings",
        lambda: _build_settings(db_path, sqlite_enable_wal=True),
    )
    monkeypatch.setattr(core_db, "_get_sqlite_runtime_version", lambda _conn: (3, 52, 0))
    _reset_db_globals(monkeypatch)

    try:
        core_db.init_db()
        engine = core_db.get_engine()
        with engine.connect() as conn:
            journal_mode = conn.execute(text("PRAGMA journal_mode")).scalar()
            synchronous = conn.execute(text("PRAGMA synchronous")).scalar()

        assert str(journal_mode).lower() == "wal"
        assert int(synchronous) == 1
    finally:
        if core_db._engine is not None:
            core_db._engine.dispose()
        _reset_db_globals(monkeypatch)


def test_init_db_leaves_delete_mode_when_wal_requested_but_runtime_too_old(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    db_path = tmp_path / "sqlite-old-runtime.db"
    monkeypatch.setattr(
        core_db,
        "get_settings",
        lambda: _build_settings(db_path, sqlite_enable_wal=True),
    )
    monkeypatch.setattr(core_db, "_get_sqlite_runtime_version", lambda _conn: (3, 51, 0))
    _reset_db_globals(monkeypatch)
    caplog.set_level("WARNING")

    try:
        core_db.init_db()
        engine = core_db.get_engine()
        with engine.connect() as conn:
            journal_mode = conn.execute(text("PRAGMA journal_mode")).scalar()

        assert str(journal_mode).lower() == "delete"
        assert any(
            "SQLite WAL requested but runtime is below minimum supported version" in message
            for message in caplog.messages
        )
    finally:
        if core_db._engine is not None:
            core_db._engine.dispose()
        _reset_db_globals(monkeypatch)


def test_run_with_sqlite_lock_retry_retries_locked_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(sqlite_write_retry_attempts=3)
    monkeypatch.setattr(core_db, "get_settings", lambda: settings)
    monkeypatch.setattr(core_db.time, "sleep", lambda _seconds: None)

    class DummySession:
        def __init__(self) -> None:
            self.rollback_calls = 0

        def rollback(self) -> None:
            self.rollback_calls += 1

    session = DummySession()
    attempts = {"count": 0}

    def _work() -> str:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise OperationalError(
                "UPDATE foo",
                {},
                sqlite3.OperationalError("database is locked"),
            )
        return "ok"

    result = core_db.run_with_sqlite_lock_retry(
        db=session,  # type: ignore[arg-type]
        component="test",
        operation="sqlite_retry",
        work=_work,
    )

    assert result == "ok"
    assert attempts["count"] == 3
    assert session.rollback_calls == 2


def test_run_with_sqlite_lock_retry_does_not_retry_non_lock_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(sqlite_write_retry_attempts=3)
    monkeypatch.setattr(core_db, "get_settings", lambda: settings)
    monkeypatch.setattr(core_db.time, "sleep", lambda _seconds: None)

    class DummySession:
        def __init__(self) -> None:
            self.rollback_calls = 0

        def rollback(self) -> None:
            self.rollback_calls += 1

    session = DummySession()
    attempts = {"count": 0}

    def _work() -> str:
        attempts["count"] += 1
        raise OperationalError(
            "UPDATE foo",
            {},
            sqlite3.OperationalError("disk I/O error"),
        )

    with pytest.raises(OperationalError):
        core_db.run_with_sqlite_lock_retry(
            db=session,  # type: ignore[arg-type]
            component="test",
            operation="sqlite_retry",
            work=_work,
        )

    assert attempts["count"] == 1
    assert session.rollback_calls == 0


def test_run_with_sqlite_lock_retry_rolls_back_before_final_lock_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(sqlite_write_retry_attempts=3)
    monkeypatch.setattr(core_db, "get_settings", lambda: settings)
    monkeypatch.setattr(core_db.time, "sleep", lambda _seconds: None)

    class DummySession:
        def __init__(self) -> None:
            self.rollback_calls = 0

        def rollback(self) -> None:
            self.rollback_calls += 1

    session = DummySession()
    attempts = {"count": 0}

    def _work() -> str:
        attempts["count"] += 1
        raise OperationalError(
            "UPDATE foo",
            {},
            sqlite3.OperationalError("database is locked"),
        )

    with pytest.raises(OperationalError):
        core_db.run_with_sqlite_lock_retry(
            db=session,  # type: ignore[arg-type]
            component="test",
            operation="sqlite_retry",
            work=_work,
        )

    assert attempts["count"] == 3
    assert session.rollback_calls == 3
