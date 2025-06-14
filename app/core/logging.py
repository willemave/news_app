import logging
import sys
from typing import Optional
from functools import lru_cache

from app.core.settings import get_settings

@lru_cache()
def setup_logging(
    name: Optional[str] = None,
    level: Optional[str] = None
) -> logging.Logger:
    """
    Set up logging configuration for the entire application.
    
    Args:
        name: Logger name (defaults to app name from settings)
        level: Log level (defaults to settings.log_level)
    
    Returns:
        Configured logger instance
    """
    settings = get_settings()
    logger_name = name or settings.app_name
    log_level = level or settings.log_level
    
    # Configure the root logger instead of a specific named logger
    # This ensures all child loggers inherit the configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remove existing handlers from root logger
    root_logger.handlers.clear()
    
    # Console handler with formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    
    # Format with more context
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    
    root_logger.addHandler(console_handler)
    
    # Also return the app-specific logger for backward compatibility
    app_logger = logging.getLogger(logger_name)
    app_logger.setLevel(getattr(logging, log_level.upper()))
    
    return app_logger

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)