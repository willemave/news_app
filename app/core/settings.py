from functools import lru_cache

from pydantic import PostgresDsn, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database - allow both PostgreSQL and SQLite for development
    database_url: PostgresDsn | str
    database_pool_size: int = 20
    database_max_overflow: int = 40

    # Application
    app_name: str = "News Aggregator"
    debug: bool = False
    log_level: str = "INFO"

    # Worker configuration
    max_workers: int = 5
    worker_timeout_seconds: int = 300
    checkout_timeout_minutes: int = 30

    # Content processing
    max_content_length: int = 100_000
    max_retry_attempts: int = 3
    max_retries: int = 3

    # External services
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    google_api_key: str | None = None

    # HTTP client
    http_timeout_seconds: int = 30
    http_max_retries: int = 3

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from existing .env

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v):
        if not v:
            raise ValueError("DATABASE_URL must be set")
        # Allow SQLite for development
        if isinstance(v, str) and v.startswith("sqlite:"):
            return v
        return v


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
