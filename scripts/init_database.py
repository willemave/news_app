#!/usr/bin/env python3
"""
Database initialization script.

Creates SQLite database and schema if they don't exist.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text

from app.core.logging import get_logger
from app.core.settings import get_settings
from app.models.schema import Base

logger = get_logger(__name__)

def create_sqlite_database(database_url: str) -> bool:
    """
    Create SQLite database directory if it doesn't exist.
    
    Args:
        database_url: SQLite connection URL
        
    Returns:
        True if database path is ready, False on failure
    """
    try:
        # Extract file path from sqlite:///path/to/db.sqlite
        if database_url.startswith('sqlite:///'):
            db_path = database_url[10:]  # Remove 'sqlite:///'
        elif database_url.startswith('sqlite://'):
            db_path = database_url[9:]   # Remove 'sqlite://'
        else:
            logger.error(f"Invalid SQLite URL format: {database_url}")
            return False
        
        # Create directory if it doesn't exist
        db_file = Path(db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"SQLite database path ready: {db_path}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to prepare SQLite database path: {e}")
        return False

def create_database_if_not_exists(database_url: str) -> bool:
    """
    Create SQLite database directory if it doesn't exist.
    
    Args:
        database_url: SQLite database connection URL
        
    Returns:
        True if database is ready, False on failure
    """
    if not database_url.startswith('sqlite:'):
        logger.error(f"Only SQLite databases are supported. Got: {database_url}")
        return False
    
    return create_sqlite_database(database_url)

def create_schema(database_url: str) -> bool:
    """
    Create database schema (tables) if they don't exist.
    
    Args:
        database_url: Database connection URL
        
    Returns:
        True if schema was created successfully, False on failure
    """
    try:
        # Create engine
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            echo=False  # Don't log SQL during initialization
        )
        
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        # Create all tables
        Base.metadata.create_all(engine)
        
        # Verify tables were created
        with engine.connect() as conn:
            # Check for our main tables in SQLite
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('contents', 'processing_tasks')"
            ))
            
            tables = [row[0] for row in result.fetchall()]
            
            if 'contents' in tables and 'processing_tasks' in tables:
                logger.info("Database schema created successfully")
                logger.info(f"Created tables: {', '.join(tables)}")
                return True
            else:
                logger.error(f"Schema creation incomplete. Found tables: {tables}")
                return False
                
    except Exception as e:
        logger.error(f"Failed to create database schema: {e}")
        return False

def verify_schema(database_url: str) -> bool:
    """
    Verify that the database schema is properly set up.
    
    Args:
        database_url: Database connection URL
        
    Returns:
        True if schema is valid, False otherwise
    """
    try:
        engine = create_engine(database_url, pool_pre_ping=True)
        
        with engine.connect() as conn:
            # Test basic operations on each table
            
            # Test contents table
            conn.execute(text("SELECT COUNT(*) FROM contents"))
            
            # Test processing_tasks table  
            conn.execute(text("SELECT COUNT(*) FROM processing_tasks"))
            
            logger.info("Database schema verification passed")
            return True
            
    except Exception as e:
        logger.error(f"Database schema verification failed: {e}")
        return False

def main():
    """Main initialization function."""
    print("🗄️  Starting database initialization...")
    logger.info("Starting database initialization...")
    
    try:
        # Get settings
        settings = get_settings()
        database_url = str(settings.database_url)
        
        print(f"📍 Database URL: {database_url}")
        logger.info(f"Database URL: {database_url}")
        
        # Step 1: Create database if it doesn't exist
        print("📁 Creating database directory if needed...")
        if not create_database_if_not_exists(database_url):
            print("❌ Failed to create database")
            logger.error("Failed to create database")
            sys.exit(1)
        
        # Step 2: Create schema (tables)
        print("🏗️  Creating database schema...")
        if not create_schema(database_url):
            print("❌ Failed to create database schema")
            logger.error("Failed to create database schema")
            sys.exit(1)
        
        # Step 3: Verify schema
        print("✅ Verifying database schema...")
        if not verify_schema(database_url):
            print("❌ Database schema verification failed")
            logger.error("Database schema verification failed")
            sys.exit(1)
        
        print("🎉 Database initialization completed successfully!")
        print(f"📊 Database ready at: {database_url}")
        logger.info("Database initialization completed successfully!")
        
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        logger.error(f"Database initialization failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()