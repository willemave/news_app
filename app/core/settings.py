import re
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings

# Load .env file into os.environ so libraries like openai/pydantic-ai can read it
load_dotenv(override=True)


class Settings(BaseSettings):
    # Database - allow both PostgreSQL and SQLite for development
    database_url: PostgresDsn | str
    database_pool_size: int = 20
    database_max_overflow: int = 40

    # Application
    app_name: str = "News Aggregator"
    debug: bool = False
    log_level: str = "INFO"

    # Authentication settings
    JWT_SECRET_KEY: str = Field(..., description="Secret key for JWT token signing")
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT signing algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=43200, description="Access token expiry in minutes (30 days)"
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=90, description="Refresh token expiry in days")
    ADMIN_PASSWORD: str = Field(..., description="Admin password for web access")

    # Worker configuration
    max_workers: int = 1
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
    exa_api_key: str | None = None

    # PDF extraction (Gemini)
    pdf_gemini_model: str = Field(
        default="gemini-flash-3",
        description="Gemini model name for PDF extraction",
    )

    # Whisper transcription settings
    whisper_model_size: str = "base"  # tiny, base, small, medium, large
    whisper_device: str = "auto"  # auto, cpu, cuda, mps

    # HTTP client
    http_timeout_seconds: int = 30
    http_max_retries: int = 3

    # Reddit / PRAW configuration (script flow)
    reddit_client_id: str | None = None
    reddit_client_secret: str | None = None
    reddit_username: str | None = None
    reddit_password: str | None = None
    reddit_read_only: bool = True
    reddit_user_agent: str | None = None

    # Storage paths
    media_base_dir: Path = Field(default_factory=lambda: Path.cwd() / "data" / "media")
    logs_base_dir: Path = Field(default_factory=lambda: Path.cwd() / "logs")

    # crawl4ai table extraction
    crawl4ai_enable_table_extraction: bool = False
    crawl4ai_table_provider: str | None = None
    crawl4ai_table_css_selector: str | None = None
    crawl4ai_table_enable_chunking: bool = True
    crawl4ai_table_chunk_token_threshold: int = 3000
    crawl4ai_table_min_rows_per_chunk: int = 10
    crawl4ai_table_max_parallel_chunks: int = 5
    crawl4ai_table_verbose: bool = False

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

    @field_validator("pdf_gemini_model")
    @classmethod
    def validate_pdf_gemini_model(cls, v: str) -> str:
        value = v.strip()
        if not value:
            raise ValueError("PDF_GEMINI_MODEL must be set")
        if not re.match(r"^gemini-[\w\.-]+$", value):
            raise ValueError("PDF_GEMINI_MODEL must start with 'gemini-'")
        return value

    @property
    def podcast_media_dir(self) -> Path:
        """Return the directory for storing podcast media files.

        Returns:
            Path: Absolute directory path for podcast media output.
        """

        return (self.media_base_dir / "podcasts").resolve()

    @property
    def substack_media_dir(self) -> Path:
        """Return the directory for storing Substack assets.

        Returns:
            Path: Absolute directory path for Substack media output.
        """

        return (self.media_base_dir / "substack").resolve()

    @property
    def logs_dir(self) -> Path:
        """Return the root directory for all log files.

        Returns:
            Path: Absolute directory path for log storage.
        """

        return self.logs_base_dir.resolve()


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
