import sqlite3
import subprocess
import sys
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

from app.core.logging import get_logger
from app.core.observability import build_log_extra
from app.core.settings import get_settings

logger = get_logger(__name__)

# SQLAlchemy declarative base
Base = declarative_base()

# Global engine instance
_engine = None
_SessionLocal = None
_sqlite_runtime_diagnostics_logged = False
_SQLITE_MIN_WAL_VERSION = (3, 52, 0)


def _sqlite_version_tuple(version: str) -> tuple[int, int, int]:
    """Parse a SQLite version string into a numeric tuple."""
    parts = [int(part) for part in version.split(".")[:3]]
    while len(parts) < 3:
        parts.append(0)
    return (parts[0], parts[1], parts[2])


def is_sqlite_lock_error(exc: BaseException) -> bool:
    """Return whether an exception chain represents SQLite lock contention."""
    candidate: BaseException | None = exc
    while candidate is not None:
        message = str(candidate).lower()
        if "database is locked" in message or "database table is locked" in message:
            return True
        if "sqlite_busy" in message:
            return True
        candidate = candidate.__cause__ or candidate.__context__
    return False


def _sqlite_runtime_diagnostics(dbapi_conn: sqlite3.Connection) -> dict[str, Any]:
    """Return runtime SQLite diagnostics after PRAGMAs are applied."""
    cursor = dbapi_conn.cursor()
    try:
        cursor.execute("SELECT sqlite_version()")
        version = str(cursor.fetchone()[0])
        cursor.execute("PRAGMA journal_mode")
        journal_mode = str(cursor.fetchone()[0]).lower()
        cursor.execute("PRAGMA busy_timeout")
        busy_timeout = int(cursor.fetchone()[0])
        cursor.execute("PRAGMA synchronous")
        synchronous = int(cursor.fetchone()[0])
        cursor.execute("PRAGMA foreign_keys")
        foreign_keys = int(cursor.fetchone()[0])
    finally:
        cursor.close()

    return {
        "sqlite_version": version,
        "journal_mode": journal_mode,
        "busy_timeout_ms": busy_timeout,
        "synchronous": synchronous,
        "foreign_keys": foreign_keys,
    }


def _log_sqlite_runtime_diagnostics_once(
    dbapi_conn: sqlite3.Connection,
    *,
    wal_requested: bool,
) -> None:
    """Emit SQLite runtime diagnostics once per process."""
    global _sqlite_runtime_diagnostics_logged
    if _sqlite_runtime_diagnostics_logged:
        return

    diagnostics = _sqlite_runtime_diagnostics(dbapi_conn)
    logger.info(
        "SQLite runtime diagnostics",
        extra=build_log_extra(
            component="database",
            operation="sqlite_runtime_diagnostics",
            status="completed",
            context_data=diagnostics
            | {
                "wal_requested": wal_requested,
                "wal_enabled": diagnostics["journal_mode"] == "wal",
            },
        ),
    )
    _sqlite_runtime_diagnostics_logged = True


def _get_sqlite_runtime_version(dbapi_conn: sqlite3.Connection) -> tuple[int, int, int]:
    """Return the runtime SQLite version tuple."""
    cursor = dbapi_conn.cursor()
    try:
        cursor.execute("SELECT sqlite_version()")
        return _sqlite_version_tuple(str(cursor.fetchone()[0]))
    finally:
        cursor.close()


def _configure_sqlite_connection(
    dbapi_conn: sqlite3.Connection,
    *,
    busy_timeout_ms: int,
    wal_requested: bool,
) -> None:
    """Apply SQLite PRAGMAs for one connection."""
    runtime_version = _get_sqlite_runtime_version(dbapi_conn)
    cursor = dbapi_conn.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
        if wal_requested and runtime_version >= _SQLITE_MIN_WAL_VERSION:
            cursor.execute("PRAGMA journal_mode=WAL")
            journal_mode = str(cursor.fetchone()[0]).lower()
            if journal_mode == "wal":
                cursor.execute("PRAGMA synchronous=NORMAL")
        else:
            cursor.execute("PRAGMA journal_mode=DELETE")
            cursor.fetchone()
            if wal_requested:
                logger.warning(
                    "SQLite WAL requested but runtime is below minimum supported version",
                    extra=build_log_extra(
                        component="database",
                        operation="sqlite_runtime_diagnostics",
                        status="degraded",
                        context_data={
                            "sqlite_version": ".".join(str(part) for part in runtime_version),
                            "wal_requested": True,
                            "minimum_wal_version": ".".join(
                                str(part) for part in _SQLITE_MIN_WAL_VERSION
                            ),
                        },
                    ),
                )
    finally:
        cursor.close()

    _log_sqlite_runtime_diagnostics_once(dbapi_conn, wal_requested=wal_requested)


def run_with_sqlite_lock_retry[T](
    *,
    db: Session,
    component: str,
    operation: str,
    work: Callable[[], T],
    item_id: str | int | None = None,
    context_data: dict[str, Any] | None = None,
) -> T:
    """Retry a short idempotent write when SQLite reports lock contention."""
    attempts = get_settings().sqlite_write_retry_attempts
    for attempt in range(1, attempts + 1):
        try:
            return work()
        except OperationalError as exc:
            if not is_sqlite_lock_error(exc) or attempt >= attempts:
                raise

            db.rollback()
            backoff_seconds = 0.05 * attempt
            logger.warning(
                "SQLite write contention detected; retrying write",
                extra=build_log_extra(
                    component=component,
                    operation=operation,
                    status="retrying",
                    item_id=item_id,
                    context_data=(context_data or {})
                    | {
                        "attempt": attempt,
                        "max_attempts": attempts,
                        "backoff_seconds": round(backoff_seconds, 3),
                    },
                ),
            )
            time.sleep(backoff_seconds)

    raise RuntimeError("SQLite retry helper exhausted without returning or raising")


def _is_sqlite_url(database_url: str) -> bool:
    """Return whether the configured database URL targets SQLite."""
    return make_url(database_url).drivername.startswith("sqlite")


def init_db():
    """Initialize database engine and session factory."""
    global _engine, _SessionLocal

    if _engine is not None:
        return

    settings = get_settings()
    database_url = str(settings.database_url)
    is_sqlite = _is_sqlite_url(database_url)

    # Create engine with connection pooling
    engine_kwargs = {
        "pool_pre_ping": True,
        "echo": settings.debug,
    }
    if is_sqlite:
        engine_kwargs["connect_args"] = {
            "check_same_thread": False,
            "timeout": settings.sqlite_busy_timeout_ms / 1000,
        }
    else:
        engine_kwargs["pool_size"] = settings.database_pool_size
        engine_kwargs["max_overflow"] = settings.database_max_overflow

    _engine = create_engine(database_url, **engine_kwargs)

    # Create session factory
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)

    if is_sqlite:

        @event.listens_for(_engine, "connect")
        def set_sqlite_pragmas(dbapi_conn, connection_record):
            _configure_sqlite_connection(
                dbapi_conn=dbapi_conn,
                busy_timeout_ms=settings.sqlite_busy_timeout_ms,
                wal_requested=settings.sqlite_enable_wal,
            )

    logger.info("Database initialized successfully")


def get_engine():
    """Get the database engine, initializing if necessary."""
    if _engine is None:
        init_db()
    return _engine


def get_session_factory():
    """Get the session factory, initializing if necessary."""
    if _SessionLocal is None:
        init_db()
    return _SessionLocal


@contextmanager
def get_db() -> Generator[Session]:
    """
    Context manager for database sessions.

    Usage:
        with get_db() as db:
            result = db.query(Content).all()
    """
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db_session() -> Generator[Session]:
    """
    Get a database session for FastAPI dependency injection.

    Yields:
        Database session that will be automatically committed and closed.
    """
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_readonly_db_session() -> Generator[Session]:
    """
    Get a read-only database session for FastAPI dependency injection.

    Yields:
        Database session that will be closed without committing.
    """
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations():
    """Run Alembic migrations to ensure database schema is up to date."""
    try:
        # Run alembic upgrade head
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            check=True,
        )
        logger.info("Database migrations completed successfully")
        if result.stdout:
            logger.debug(f"Migration output: {result.stdout}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Database migration failed: {e}")
        if e.stderr:
            logger.error(f"Migration error output: {e.stderr}")
        raise RuntimeError("Failed to run database migrations") from e
