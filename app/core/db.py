from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import Pool

from app.core.settings import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Global engine instance
_engine = None
_SessionLocal = None

def init_db():
    """Initialize database engine and session factory."""
    global _engine, _SessionLocal
    
    if _engine is not None:
        return
    
    settings = get_settings()
    
    # Create engine with connection pooling
    _engine = create_engine(
        str(settings.database_url),
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_pre_ping=True,  # Verify connections before using
        echo=settings.debug,  # Log SQL in debug mode
    )
    
    # Create session factory
    _SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=_engine
    )
    
    # Add connection pool logging
    @event.listens_for(Pool, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        logger.debug(f"New database connection established: {id(dbapi_conn)}")
    
    @event.listens_for(Pool, "checkout")
    def log_checkout(dbapi_conn, connection_record, connection_proxy):
        logger.debug(f"Connection checked out from pool: {id(dbapi_conn)}")
    
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
def get_db() -> Generator[Session, None, None]:
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

def get_db_session() -> Session:
    """
    Get a database session (for dependency injection).
    
    Note: Caller is responsible for closing the session.
    """
    SessionLocal = get_session_factory()
    return SessionLocal()