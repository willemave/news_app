# News App Architecture

> Comprehensive technical documentation of the codebase structure, patterns, and implementation details.

**Last Updated**: November 2025
**Python Version**: 3.13+
**Framework**: FastAPI + SQLAlchemy 2.x
**Client**: SwiftUI (iOS 17+)

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Core Infrastructure](#2-core-infrastructure)
3. [Database Layer](#3-database-layer)
4. [Pydantic Type System](#4-pydantic-type-system)
5. [API Layer](#5-api-layer)
6. [Services Layer](#6-services-layer)
7. [Content Pipeline](#7-content-pipeline)
8. [Processing Strategies](#8-processing-strategies)
9. [Scrapers](#9-scrapers)
10. [iOS Client Architecture](#10-ios-client-architecture)
11. [Architectural Patterns](#11-architectural-patterns)
12. [Data Flow Diagrams](#12-data-flow-diagrams)
13. [Security Architecture](#13-security-architecture)
14. [Deep Dive Chat System](#14-deep-dive-chat-system)

---

## 1. System Overview

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              NEWS APP SYSTEM                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────────────┐   │
│  │   iOS App    │────│  FastAPI     │────│     SQLite/PostgreSQL       │   │
│  │   (SwiftUI)  │    │  Backend     │    │     Database                 │   │
│  └──────────────┘    └──────────────┘    └──────────────────────────────┘   │
│         │                   │                          │                     │
│         │            ┌──────┴──────┐                   │                     │
│         │            │             │                   │                     │
│    ┌────┴────┐  ┌────┴────┐  ┌─────┴─────┐    ┌───────┴───────┐            │
│    │ Apple   │  │ Content │  │ Task      │    │   Content     │            │
│    │ Sign In │  │ API     │  │ Queue     │    │   Scrapers    │            │
│    └─────────┘  └─────────┘  └───────────┘    └───────────────┘            │
│                                   │                   │                     │
│                           ┌───────┴───────┐           │                     │
│                           │    Workers    │───────────┘                     │
│                           │  (Pipeline)   │                                 │
│                           └───────────────┘                                 │
│                                   │                                         │
│                    ┌──────────────┼──────────────┐                          │
│                    │              │              │                          │
│              ┌─────┴─────┐ ┌──────┴─────┐ ┌─────┴─────┐                     │
│              │  LLM      │ │  Whisper   │ │ Crawl4AI  │                     │
│              │  Services │ │ (Local)    │ │ Extractor │                     │
│              └───────────┘ └────────────┘ └───────────┘                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Component Responsibilities

| Component | Purpose |
|-----------|---------|
| **FastAPI Backend** | REST API, authentication, web admin interface |
| **Content Pipeline** | Task queue, content processing, LLM summarization |
| **Scrapers** | Multi-source content discovery (HN, Reddit, Substack, etc.) |
| **iOS Client** | Native mobile interface with offline support |
| **LLM Services** | Content summarization (Anthropic, OpenAI, Google) |
| **Whisper** | Local audio transcription for podcasts |
| **Crawl4AI** | HTML content extraction with browser automation |

### 1.3 Directory Structure

```
app/
├── core/                          # Infrastructure layer
│   ├── db.py                     # Database engine & sessions
│   ├── settings.py               # Configuration management
│   ├── security.py               # JWT & authentication
│   ├── deps.py                   # FastAPI dependencies
│   └── logging.py                # Logging configuration
│
├── models/                        # Data models
│   ├── schema.py                 # SQLAlchemy ORM models
│   ├── user.py                   # User model & auth schemas
│   ├── metadata.py               # Content metadata schemas
│   └── pagination.py             # Pagination models
│
├── routers/                       # API endpoints
│   ├── auth.py                   # Authentication routes
│   ├── content.py                # Web UI routes
│   ├── admin.py                  # Admin dashboard
│   └── api/                      # REST API endpoints
│
├── services/                      # Business logic
│   ├── anthropic_llm.py          # Anthropic Claude
│   ├── openai_llm.py             # OpenAI GPT
│   ├── google_flash.py           # Google Gemini
│   ├── favorites.py              # User favorites
│   ├── read_status.py            # Read tracking
│   └── queue.py                  # Task queue
│
├── pipeline/                      # Task processing
│   ├── worker.py                 # Content processor
│   ├── podcast_workers.py        # Audio processing
│   ├── checkout.py               # Worker locking
│   └── sequential_task_processor.py
│
├── processing_strategies/         # Content extractors
│   ├── registry.py               # Strategy registry
│   ├── html_strategy.py          # HTML/web pages
│   ├── pdf_strategy.py           # PDF documents
│   ├── youtube_strategy.py       # YouTube videos
│   └── ...                       # Other strategies
│
├── scraping/                      # Content scrapers
│   ├── runner.py                 # Scraper orchestrator
│   ├── base.py                   # Base scraper class
│   └── *_unified.py              # Per-source scrapers
│
└── http_client/                   # Network layer
    └── robust_http_client.py     # Resilient HTTP client
```

---

## 2. Core Infrastructure

### 2.1 Database Management (`app/core/db.py`)

The database layer uses SQLAlchemy 2.x with lazy initialization and connection pooling.

```python
# Key exports
Base: DeclarativeBase           # ORM base class
init_db() -> None               # Initialize engine & run migrations
get_db() -> Generator[Session]  # Context manager for sessions
get_db_session() -> Session     # FastAPI dependency
```

**Engine Configuration:**
```python
engine = create_engine(
    settings.database_url,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True,          # Verify connections before use
    pool_recycle=3600,           # Recycle connections after 1 hour
)
```

**Session Pattern:**
```python
@contextmanager
def get_db() -> Generator[Session, None, None]:
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

### 2.2 Configuration (`app/core/settings.py`)

Pydantic v2 BaseSettings for type-safe configuration from environment variables.

```python
class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite:///./news_app.db"
    pool_size: int = 20
    max_overflow: int = 40

    # Authentication
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 90
    ADMIN_PASSWORD: str

    # LLM Services
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    google_api_key: str | None = None

    # Processing
    whisper_model_size: str = "base"
    whisper_device: str = "auto"
    max_content_length: int = 100000

    # Storage
    media_base_dir: str = "./media"
    logs_base_dir: str = "./logs"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

# Singleton access
@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### 2.3 Security (`app/core/security.py`)

JWT token generation and validation with Apple Sign In support.

```python
# Token generation
def create_access_token(user_id: int) -> str:
    """Generate 30-minute access token."""
    return create_token(user_id, "access", timedelta(minutes=30))

def create_refresh_token(user_id: int) -> str:
    """Generate 90-day refresh token."""
    return create_token(user_id, "refresh", timedelta(days=90))

# Token structure
{
    "sub": str(user_id),
    "type": "access" | "refresh",
    "exp": datetime,
    "iat": datetime
}

# Verification
def verify_token(token: str) -> dict:
    """Decode and validate JWT, raises jwt.InvalidTokenError on failure."""
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
```

### 2.4 FastAPI Dependencies (`app/core/deps.py`)

Authentication middleware for endpoint protection.

```python
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db_session),
) -> User:
    """Extract and validate user from JWT Bearer token.

    Raises:
        HTTPException(401): Invalid/expired token or inactive user
    """
    token = credentials.credentials
    claims = verify_token(token)

    if claims.get("type") != "access":
        raise HTTPException(401, "Invalid token type")

    user = db.query(User).filter(User.id == int(claims["sub"])).first()
    if not user or not user.is_active:
        raise HTTPException(401, "User not found or inactive")

    return user

async def get_optional_user(...) -> User | None:
    """Same as get_current_user but returns None on auth failure."""

async def require_admin(request: Request) -> None:
    """Verify admin session cookie exists.

    Used for web admin routes. Sessions stored in-memory.
    """
    session_id = request.cookies.get("admin_session")
    if session_id not in admin_sessions:
        raise HTTPException(401, "Admin authentication required")
```

### 2.5 Logging (`app/core/logging.py`)

Centralized logging configuration with structured output.

```python
def setup_logging(name: str, level: int = logging.INFO) -> logging.Logger:
    """Configure root logger with console handler.

    Format: "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
    """
    logger = logging.getLogger()  # Root logger
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(handler)
    logger.setLevel(level)
    return logging.getLogger(name)
```

---

## 3. Database Layer

### 3.1 Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            DATABASE SCHEMA                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────┐           ┌───────────────────┐                         │
│  │     users      │           │     contents      │                         │
│  ├────────────────┤           ├───────────────────┤                         │
│  │ id (PK)        │           │ id (PK)           │                         │
│  │ apple_id (UQ)  │           │ content_type      │◄─┐                      │
│  │ email (UQ)     │           │ url (UQ w/type)   │  │                      │
│  │ full_name      │           │ title             │  │                      │
│  │ is_admin       │           │ source            │  │                      │
│  │ is_active      │           │ platform          │  │                      │
│  │ created_at     │           │ is_aggregate      │  │                      │
│  │ updated_at     │           │ status            │  │                      │
│  └────────┬───────┘           │ content_metadata  │  │                      │
│           │                   │ ...               │  │                      │
│           │                   └───────────────────┘  │                      │
│           │                            ▲             │                      │
│           │                            │             │                      │
│           │    ┌───────────────────────┼─────────────┼──────────────┐       │
│           │    │                       │             │              │       │
│           ▼    ▼                       │             │              │       │
│  ┌────────────────────┐  ┌─────────────────────┐  ┌──────────────────┐     │
│  │ content_read_status│  │ content_favorites   │  │ content_unlikes  │     │
│  ├────────────────────┤  ├─────────────────────┤  ├──────────────────┤     │
│  │ id (PK)            │  │ id (PK)             │  │ id (PK)          │     │
│  │ user_id (FK→users) │  │ user_id (FK→users)  │  │ user_id          │     │
│  │ content_id (FK)    │  │ content_id (FK)     │  │ content_id       │     │
│  │ read_at            │  │ favorited_at        │  │ unliked_at       │     │
│  │ created_at         │  │ created_at          │  │ created_at       │     │
│  └────────────────────┘  └─────────────────────┘  └──────────────────┘     │
│                                                                              │
│  ┌────────────────────┐  ┌─────────────────────┐                            │
│  │ processing_tasks   │  │ event_logs          │                            │
│  ├────────────────────┤  ├─────────────────────┤                            │
│  │ id (PK)            │  │ id (PK)             │                            │
│  │ task_type          │  │ event_type          │                            │
│  │ content_id         │  │ event_name          │                            │
│  │ payload (JSON)     │  │ status              │                            │
│  │ status             │  │ data (JSON)         │                            │
│  │ created_at         │  │ created_at          │                            │
│  │ started_at         │  └─────────────────────┘                            │
│  │ completed_at       │                                                     │
│  │ error_message      │                                                     │
│  │ retry_count        │                                                     │
│  └────────────────────┘                                                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Content Model (`app/models/schema.py`)

The `Content` model is the central entity for all scraped and processed content.

```python
class Content(Base):
    __tablename__ = "contents"

    # Primary identification
    id: Mapped[int] = mapped_column(primary_key=True)
    content_type: Mapped[str] = mapped_column(String(20), index=True)  # article|podcast|news
    url: Mapped[str] = mapped_column(String(2048))

    # Metadata
    title: Mapped[str | None] = mapped_column(String(500))
    source: Mapped[str | None] = mapped_column(String(100), index=True)    # e.g., "Import AI"
    platform: Mapped[str | None] = mapped_column(String(50), index=True)   # e.g., "substack"
    is_aggregate: Mapped[bool] = mapped_column(default=False, index=True)  # News digest flag

    # Processing state
    status: Mapped[str] = mapped_column(String(20), default="new", index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(default=0)
    classification: Mapped[str | None] = mapped_column(String(20), index=True)  # to_read|skip

    # Worker checkout (distributed locking)
    checked_out_by: Mapped[str | None] = mapped_column(String(100), index=True)
    checked_out_at: Mapped[datetime | None]

    # Type-specific data (validated by Pydantic)
    content_metadata: Mapped[dict] = mapped_column(JSON, default=dict)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    processed_at: Mapped[datetime | None]
    publication_date: Mapped[datetime | None] = mapped_column(index=True)

    # Constraints
    __table_args__ = (
        UniqueConstraint("url", "content_type", name="uq_url_content_type"),
        Index("idx_content_type_status", "content_type", "status"),
        Index("idx_checkout", "checked_out_by", "checked_out_at"),
    )
```

**Content Types:**
| Type | Description | Metadata Model |
|------|-------------|----------------|
| `article` | Web articles, blog posts, papers | `ArticleMetadata` |
| `podcast` | Audio/video episodes | `PodcastMetadata` |
| `news` | Aggregated news items (HN, Techmeme) | `NewsMetadata` |

**Status Lifecycle:**
```
new → pending → processing → completed
                    ↓
                  failed → (retry) → processing
                    ↓
                 skipped
```

### 3.3 User Model

```python
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    apple_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now())
```

### 3.4 User State Tables

```python
class ContentReadStatus(Base):
    """Tracks which content a user has read."""
    __tablename__ = "content_read_status"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(index=True)
    content_id: Mapped[int] = mapped_column(index=True)
    read_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "content_id"),
    )

class ContentFavorites(Base):
    """User's saved/favorited content."""
    __tablename__ = "content_favorites"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(index=True)
    content_id: Mapped[int] = mapped_column(index=True)
    favorited_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "content_id"),
    )
```

### 3.5 Processing Task Queue

```python
class ProcessingTask(Base):
    """Database-backed task queue for async processing."""
    __tablename__ = "processing_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_type: Mapped[str] = mapped_column(String(50), index=True)
    content_id: Mapped[int | None] = mapped_column(index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    started_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(default=0)

    __table_args__ = (
        Index("idx_task_status_created", "status", "created_at"),
    )
```

**Task Types:**
- `SCRAPE` - Run a scraper
- `PROCESS_CONTENT` - Extract and summarize content
- `DOWNLOAD_AUDIO` - Download podcast audio
- `TRANSCRIBE` - Transcribe audio with Whisper
- `SUMMARIZE` - LLM summarization

### 3.6 Event Logging

```python
class EventLog(Base):
    """Flexible structured event logging."""
    __tablename__ = "event_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(50), index=True)   # scraper_run, processing_batch
    event_name: Mapped[str | None] = mapped_column(String(100), index=True)  # scraper name
    status: Mapped[str | None] = mapped_column(String(20), index=True)  # started, completed, failed
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)
```

---

## 4. Pydantic Type System

### 4.1 Content Type Enums

```python
class ContentType(str, Enum):
    ARTICLE = "article"
    PODCAST = "podcast"
    NEWS = "news"

class ContentStatus(str, Enum):
    NEW = "new"
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class ContentClassification(str, Enum):
    TO_READ = "to_read"
    SKIP = "skip"
```

### 4.2 Structured Summary Models

```python
class SummaryBulletPoint(BaseModel):
    """Individual insight or key point."""
    text: str = Field(..., min_length=10, max_length=500)
    category: str | None = None  # e.g., "key_insight", "action_item"

class ContentQuote(BaseModel):
    """Notable quote from content."""
    text: str = Field(..., min_length=10, max_length=5000)
    context: str | None = None  # Attribution or context

class StructuredSummary(BaseModel):
    """Comprehensive LLM-generated summary for articles/podcasts."""
    title: str
    overview: str                        # 2-3 sentence summary
    bullet_points: list[SummaryBulletPoint] = []
    quotes: list[ContentQuote] = []
    topics: list[str] = []              # Main topics/themes
    questions: list[str] = []           # Follow-up questions
    counter_arguments: list[str] = []   # Alternative viewpoints
    summarization_date: datetime | None
    classification: ContentClassification | None
    full_markdown: str | None           # Full summary in markdown
```

### 4.3 Type-Specific Metadata

```python
class ArticleMetadata(BaseModel):
    """Metadata for web articles and blog posts."""
    source: str | None = None
    content: str | None = None              # Raw extracted text
    author: str | None = None
    publication_date: datetime | None = None
    content_type: str | None = None         # html|pdf|text|markdown
    final_url_after_redirects: str | None = None
    word_count: int | None = None
    summary: StructuredSummary | None = None

class PodcastMetadata(BaseModel):
    """Metadata for audio/video episodes."""
    source: str | None = None
    audio_url: str | None = None
    transcript: str | None = None
    duration: int | None = None             # Seconds
    episode_number: str | None = None

    # YouTube-specific
    video_url: str | None = None
    video_id: str | None = None
    channel_name: str | None = None
    thumbnail_url: str | None = None
    view_count: int | None = None
    like_count: int | None = None
    has_transcript: bool = False

    word_count: int | None = None
    summary: StructuredSummary | None = None

class NewsMetadata(BaseModel):
    """Metadata for news/aggregated items."""
    source: str | None = None
    platform: str | None = None
    article: NewsArticleMetadata | None = None
    aggregator: NewsAggregatorMetadata | None = None
    discovery_time: datetime | None = None
    summary: NewsSummary | None = None

class NewsSummary(BaseModel):
    """Compact summary for quick-scanning news."""
    title: str | None = None
    article_url: str | None = None
    key_points: list[str] = Field(default=[], alias="bullet_points")
    summary: str | None = Field(None, alias="overview")
    classification: ContentClassification | None = None
    summarization_date: datetime | None = None
```

### 4.4 ContentData Unified Wrapper

```python
class ContentData(BaseModel):
    """Unified wrapper for Content ORM + typed metadata."""
    id: int | None = None
    content_type: ContentType
    url: str
    title: str | None = None
    status: ContentStatus = ContentStatus.NEW

    # Polymorphic metadata
    metadata: ArticleMetadata | PodcastMetadata | NewsMetadata

    platform: str | None = None
    source: str | None = None
    is_aggregate: bool = False

    error_message: str | None = None
    retry_count: int = 0

    created_at: datetime | None = None
    processed_at: datetime | None = None
    publication_date: datetime | None = None

    @property
    def summary(self) -> StructuredSummary | NewsSummary | None:
        """Access summary from typed metadata."""
        return self.metadata.summary if self.metadata else None

    @property
    def display_title(self) -> str:
        """Fallback to summary title or 'Untitled'."""
        return self.title or (self.summary.title if self.summary else None) or "Untitled"
```

### 4.5 API Response Models

```python
class ContentSummaryResponse(BaseModel):
    """List view representation (29 fields)."""
    id: int
    content_type: str
    url: str
    title: str | None
    source: str | None
    platform: str | None
    is_aggregate: bool
    status: str
    classification: str | None

    # Dates
    created_at: datetime
    updated_at: datetime
    processed_at: datetime | None
    publication_date: datetime | None

    # User state
    is_read: bool = False
    is_favorited: bool = False

    # News-specific fields (for iOS fast rendering)
    news_title: str | None = None
    news_summary: str | None = None
    news_key_points: list[str] = []
    news_classification: str | None = None
    news_article_url: str | None = None

    # Embedded metadata
    article_metadata: ArticleMetadata | None = None
    podcast_metadata: PodcastMetadata | None = None
    news_metadata: NewsMetadata | None = None

class ContentDetailResponse(ContentSummaryResponse):
    """Detail view with full summary (33 fields)."""
    bullet_points: list[SummaryBulletPoint] = []
    quotes: list[ContentQuote] = []
    topics: list[str] = []
    questions: list[str] = []
    counter_arguments: list[str] = []
    overview: str | None = None
    full_markdown: str | None = None

class ContentListResponse(BaseModel):
    """Paginated list response."""
    contents: list[ContentSummaryResponse]
    total: int
    available_dates: list[str]      # For date filter UI
    content_types: list[str]        # For type filter UI
    next_cursor: str | None
    has_more: bool
    page_size: int
```

### 4.6 Pagination

```python
class PaginationCursorData(BaseModel):
    """Opaque cursor internals."""
    last_id: int
    last_created_at: datetime
    filters_hash: str | None = None  # Detect filter changes

class PaginationMetadata(BaseModel):
    """Pagination info in responses."""
    next_cursor: str | None      # Base64-encoded PaginationCursorData
    has_more: bool
    page_size: int
    total: int | None = None     # May be omitted for performance
```

---

## 5. API Layer

### 5.1 Router Structure

```
/auth                              # Authentication
├── POST /apple                    # Apple Sign In
├── POST /refresh                  # Refresh tokens
├── GET  /me                       # Current user info
├── POST /admin/login              # Admin web login
└── POST /admin/logout             # Admin logout

/api/content                       # REST API (JWT required)
├── GET  /                         # List with pagination
├── GET  /search                   # Full-text search
├── GET  /unread-counts            # Badge counts
├── GET  /{id}                     # Content detail
├── GET  /{id}/chatgpt-url         # ChatGPT deep link
├── POST /{id}/mark-read           # Mark as read
├── POST /bulk-mark-read           # Bulk mark read
├── POST /{id}/favorites/toggle    # Toggle favorite
├── GET  /favorites                # List favorites
└── POST /{id}/convert             # Convert news→article

/                                  # Web admin (session required)
├── GET  /                         # Content list
├── GET  /content/{id}             # Content detail
└── GET  /favorites                # Favorites page

/admin                             # Admin dashboard
├── GET  /                         # Dashboard
├── GET  /logs                     # Log viewer
└── GET  /errors                   # Error analysis

/static                            # Static files (CSS, JS)
```

### 5.2 Authentication Endpoints

```python
@router.post("/apple", response_model=TokenResponse)
async def apple_sign_in(
    request: AppleSignInRequest,
    db: Session = Depends(get_db_session),
) -> TokenResponse:
    """
    Authenticate via Apple Sign In.

    Flow:
    1. Validate Apple id_token (MVP: no signature verification)
    2. Extract claims (sub, email)
    3. Find or create user
    4. Generate JWT tokens
    """
    claims = verify_apple_token(request.id_token)
    apple_id = claims["sub"]

    user = db.query(User).filter(User.apple_id == apple_id).first()
    if not user:
        user = User(
            apple_id=apple_id,
            email=request.email or claims.get("email"),
            full_name=request.full_name,
        )
        db.add(user)
        db.commit()

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )

@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh_token(request: RefreshTokenRequest) -> AccessTokenResponse:
    """
    Refresh access token using refresh token.

    Implements token rotation: new refresh token issued each time.
    """
    claims = verify_token(request.refresh_token)
    if claims.get("type") != "refresh":
        raise HTTPException(401, "Invalid token type")

    user_id = int(claims["sub"])
    return AccessTokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
        token_type="bearer",
    )
```

### 5.3 Content List API

```python
@router.get("/", response_model=ContentListResponse)
async def list_content(
    content_type: list[str] = Query(default=[]),  # Repeated param
    date: str | None = None,                      # YYYY-MM-DD
    read_filter: str = "all",                     # all|read|unread
    cursor: str | None = None,
    limit: int = Query(default=20, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> ContentListResponse:
    """
    List content with filtering and cursor pagination.

    Filters:
    - content_type: Filter by type(s)
    - date: Filter by created_at date
    - read_filter: Include read/unread/all

    Pagination:
    - Cursor-based for stable pagination
    - Encodes (last_id, last_created_at, filters_hash)
    """
    query = db.query(Content).filter(Content.status == "completed")

    # Apply filters
    if content_type:
        query = query.filter(Content.content_type.in_(content_type))
    if date:
        query = query.filter(func.date(Content.created_at) == date)

    # Read status filter
    read_ids = get_read_content_ids(db, user.id)
    if read_filter == "unread":
        query = query.filter(~Content.id.in_(read_ids))
    elif read_filter == "read":
        query = query.filter(Content.id.in_(read_ids))

    # Cursor pagination
    if cursor:
        cursor_data = decode_cursor(cursor)
        query = query.filter(
            or_(
                Content.created_at < cursor_data.last_created_at,
                and_(
                    Content.created_at == cursor_data.last_created_at,
                    Content.id < cursor_data.last_id,
                ),
            )
        )

    # Execute with limit+1 to detect has_more
    items = query.order_by(Content.created_at.desc(), Content.id.desc()).limit(limit + 1).all()
    has_more = len(items) > limit
    items = items[:limit]

    # Build response
    return ContentListResponse(
        contents=[to_summary_response(item, user.id, db) for item in items],
        total=query.count(),
        available_dates=get_available_dates(db),
        content_types=["article", "podcast", "news"],
        next_cursor=encode_cursor(items[-1]) if has_more else None,
        has_more=has_more,
        page_size=limit,
    )
```

### 5.4 Content Detail API

```python
@router.get("/{content_id}", response_model=ContentDetailResponse)
async def get_content_detail(
    content_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> ContentDetailResponse:
    """
    Get full content detail including structured summary.

    Extracts from content_metadata:
    - bullet_points, quotes, topics, questions
    - overview, full_markdown
    """
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(404, "Content not found")

    return to_detail_response(content, user.id, db)
```

---

## 6. Services Layer

### 6.1 Favorites Service (`app/services/favorites.py`)

```python
def toggle_favorite(
    db: Session,
    content_id: int,
    user_id: int,
) -> tuple[bool, ContentFavorites | None]:
    """Toggle favorite status, returns (is_now_favorited, record)."""
    existing = db.query(ContentFavorites).filter(
        ContentFavorites.user_id == user_id,
        ContentFavorites.content_id == content_id,
    ).first()

    if existing:
        db.delete(existing)
        return False, None
    else:
        favorite = ContentFavorites(user_id=user_id, content_id=content_id)
        db.add(favorite)
        return True, favorite

def get_favorite_content_ids(db: Session, user_id: int) -> set[int]:
    """Get all favorited content IDs for user."""
    results = db.query(ContentFavorites.content_id).filter(
        ContentFavorites.user_id == user_id
    ).all()
    return {r[0] for r in results}

def is_content_favorited(db: Session, content_id: int, user_id: int) -> bool:
    """Check if specific content is favorited."""
    return db.query(ContentFavorites).filter(
        ContentFavorites.user_id == user_id,
        ContentFavorites.content_id == content_id,
    ).first() is not None
```

### 6.2 Read Status Service (`app/services/read_status.py`)

```python
def mark_content_as_read(
    db: Session,
    content_id: int,
    user_id: int,
) -> ContentReadStatus:
    """Mark content as read, idempotent."""
    existing = db.query(ContentReadStatus).filter(
        ContentReadStatus.user_id == user_id,
        ContentReadStatus.content_id == content_id,
    ).first()

    if existing:
        return existing

    status = ContentReadStatus(user_id=user_id, content_id=content_id)
    db.add(status)
    return status

def mark_contents_as_read(
    db: Session,
    content_ids: list[int],
    user_id: int,
) -> int:
    """Bulk mark as read with fallback to individual on constraint violation."""
    existing = db.query(ContentReadStatus.content_id).filter(
        ContentReadStatus.user_id == user_id,
        ContentReadStatus.content_id.in_(content_ids),
    ).all()
    existing_ids = {r[0] for r in existing}

    new_ids = [cid for cid in content_ids if cid not in existing_ids]

    try:
        db.bulk_insert_mappings(ContentReadStatus, [
            {"user_id": user_id, "content_id": cid}
            for cid in new_ids
        ])
        return len(new_ids)
    except IntegrityError:
        db.rollback()
        # Fallback to individual inserts
        count = 0
        for cid in new_ids:
            try:
                mark_content_as_read(db, cid, user_id)
                count += 1
            except IntegrityError:
                db.rollback()
        return count
```

### 6.3 Queue Service (`app/services/queue.py`)

```python
class QueueService:
    """Database-backed task queue with row-level locking."""

    def __init__(self, db: Session):
        self.db = db

    def enqueue(
        self,
        task_type: str,
        content_id: int | None = None,
        payload: dict | None = None,
    ) -> int:
        """Add task to queue, returns task_id."""
        task = ProcessingTask(
            task_type=task_type,
            content_id=content_id,
            payload=payload or {},
            status="pending",
        )
        self.db.add(task)
        self.db.commit()
        return task.id

    def dequeue(
        self,
        task_type: str | None = None,
        worker_id: str = "default",
    ) -> dict | None:
        """
        Atomically claim next pending task.

        Uses FOR UPDATE SKIP LOCKED for distributed safety.
        """
        query = self.db.query(ProcessingTask).filter(
            ProcessingTask.status == "pending"
        )

        if task_type:
            query = query.filter(ProcessingTask.task_type == task_type)

        # Atomic claim with row lock
        task = query.order_by(ProcessingTask.created_at).with_for_update(
            skip_locked=True
        ).first()

        if not task:
            return None

        task.status = "processing"
        task.started_at = datetime.utcnow()
        self.db.commit()

        return {
            "task_id": task.id,
            "task_type": task.task_type,
            "content_id": task.content_id,
            "payload": task.payload,
        }

    def complete_task(
        self,
        task_id: int,
        success: bool = True,
        error_message: str | None = None,
    ) -> None:
        """Mark task as completed or failed."""
        task = self.db.query(ProcessingTask).get(task_id)
        task.status = "completed" if success else "failed"
        task.completed_at = datetime.utcnow()
        task.error_message = error_message
        self.db.commit()
```

### 6.4 LLM Services

All LLM services follow a common pattern:

```python
class AnthropicSummarizationService:
    """Summarization using Anthropic Claude."""

    MODEL = "claude-haiku-4-5-20251001"

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    @retry(
        retry=retry_if_exception_type((anthropic.APIError, anthropic.RateLimitError)),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(3),
    )
    def summarize_content(
        self,
        content: str,
        content_type: ContentType,
        title: str | None = None,
    ) -> StructuredSummary | NewsSummary:
        """
        Generate structured summary from content.

        Uses appropriate prompt template based on content_type.
        Parses JSON from markdown code blocks.
        Applies JSON repair for truncated responses.
        """
        prompt = get_summarization_prompt(content_type, content, title)

        response = self.client.messages.create(
            model=self.MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        raw_text = response.content[0].text
        json_str = extract_json_from_markdown(raw_text)
        json_str = repair_json_if_needed(json_str)

        data = json.loads(json_str)

        if content_type == ContentType.NEWS:
            return NewsSummary.model_validate(data)
        return StructuredSummary.model_validate(data)
```

### 6.5 Event Logger (`app/services/event_logger.py`)

```python
def log_event(
    db: Session,
    event_type: str,
    event_name: str | None = None,
    status: str | None = None,
    **data,
) -> int:
    """Log structured event, returns event_id."""
    event = EventLog(
        event_type=event_type,
        event_name=event_name,
        status=status,
        data=data,
    )
    db.add(event)
    db.commit()
    return event.id

@contextmanager
def track_event(
    db: Session,
    event_type: str,
    event_name: str | None = None,
    **initial_data,
):
    """
    Context manager for event lifecycle tracking.

    Logs 'started' on entry, 'completed' or 'failed' on exit.
    Includes duration in final event.
    """
    start = datetime.utcnow()
    log_event(db, event_type, event_name, "started", **initial_data)

    try:
        yield
        duration = (datetime.utcnow() - start).total_seconds()
        log_event(db, event_type, event_name, "completed", duration=duration, **initial_data)
    except Exception as e:
        duration = (datetime.utcnow() - start).total_seconds()
        log_event(db, event_type, event_name, "failed", duration=duration, error=str(e), **initial_data)
        raise
```

---

## 7. Content Pipeline

### 7.1 Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CONTENT PIPELINE                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐        │
│  │    Scrapers     │────▶│   Content DB    │────▶│   Task Queue    │        │
│  │  (Discovery)    │     │  (status: new)  │     │ (PROCESS_CONTENT)│       │
│  └─────────────────┘     └─────────────────┘     └────────┬────────┘        │
│                                                           │                  │
│                                                           ▼                  │
│                                              ┌─────────────────────┐         │
│                                              │ SequentialTaskProcessor│      │
│                                              │   (Orchestrator)     │        │
│                                              └──────────┬──────────┘         │
│                                                         │                    │
│                          ┌──────────────────────────────┼──────────────┐    │
│                          │                              │              │    │
│                          ▼                              ▼              ▼    │
│               ┌───────────────────┐      ┌─────────────────┐  ┌───────────┐│
│               │   ContentWorker   │      │ PodcastDownload │  │ Transcribe││
│               │ (Articles/News)   │      │    Worker       │  │  Worker   ││
│               └─────────┬─────────┘      └────────┬────────┘  └─────┬─────┘│
│                         │                         │                  │      │
│                         ▼                         ▼                  ▼      │
│               ┌───────────────────┐      ┌─────────────────┐  ┌───────────┐│
│               │ Strategy Registry │      │   Audio Files   │  │  Whisper  ││
│               │  (URL Matching)   │      │                 │  │  (Local)  ││
│               └─────────┬─────────┘      └─────────────────┘  └───────────┘│
│                         │                                                   │
│         ┌───────────────┼───────────────┬───────────────┐                  │
│         ▼               ▼               ▼               ▼                  │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐           │
│  │ HTML       │  │ PDF        │  │ YouTube    │  │ HackerNews │           │
│  │ Strategy   │  │ Strategy   │  │ Strategy   │  │ Strategy   │           │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘           │
│        │               │               │               │                   │
│        └───────────────┴───────────────┴───────────────┘                   │
│                                │                                            │
│                                ▼                                            │
│                    ┌───────────────────┐                                   │
│                    │   LLM Service     │                                   │
│                    │ (Summarization)   │                                   │
│                    └─────────┬─────────┘                                   │
│                              │                                              │
│                              ▼                                              │
│                    ┌───────────────────┐                                   │
│                    │   Content DB      │                                   │
│                    │ (status: completed)│                                  │
│                    └───────────────────┘                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Checkout Manager (`app/pipeline/checkout.py`)

Distributed worker locking using database row-level locks.

```python
class CheckoutManager:
    """Manage content checkout for distributed processing."""

    def __init__(self, db: Session, timeout_minutes: int = 30):
        self.db = db
        self.timeout_minutes = timeout_minutes

    @contextmanager
    def checkout_content(
        self,
        worker_id: str,
        content_type: ContentType | None = None,
        batch_size: int = 10,
    ) -> Generator[list[Content], None, None]:
        """
        Atomically check out content for processing.

        Uses FOR UPDATE SKIP LOCKED to prevent double-processing.
        Auto-releases on context exit (success or failure).
        """
        items = self._checkout_batch(worker_id, content_type, batch_size)

        try:
            yield items
            # Success: mark completed in caller
        except Exception:
            # Failure: release locks
            for item in items:
                self._checkin(item.id, worker_id, "pending", None)
            raise

    def _checkout_batch(
        self,
        worker_id: str,
        content_type: ContentType | None,
        batch_size: int,
    ) -> list[Content]:
        """Claim batch of pending content with row lock."""
        query = self.db.query(Content).filter(
            Content.status == "new",
            Content.checked_out_by.is_(None),
        )

        if content_type:
            query = query.filter(Content.content_type == content_type.value)

        items = query.with_for_update(skip_locked=True).limit(batch_size).all()

        for item in items:
            item.checked_out_by = worker_id
            item.checked_out_at = datetime.utcnow()
            item.status = "processing"

        self.db.commit()
        return items

    def _checkin(
        self,
        content_id: int,
        worker_id: str,
        new_status: str,
        error_message: str | None,
    ) -> None:
        """Release content lock and update status."""
        content = self.db.query(Content).get(content_id)
        if content and content.checked_out_by == worker_id:
            content.checked_out_by = None
            content.checked_out_at = None
            content.status = new_status
            if error_message:
                content.error_message = error_message
            self.db.commit()

    def release_stale_checkouts(self) -> int:
        """Release checkouts that exceeded timeout."""
        cutoff = datetime.utcnow() - timedelta(minutes=self.timeout_minutes)

        count = self.db.query(Content).filter(
            Content.checked_out_at < cutoff,
            Content.checked_out_by.isnot(None),
        ).update({
            "checked_out_by": None,
            "checked_out_at": None,
            "status": "pending",
        })

        self.db.commit()
        return count
```

### 7.3 Content Worker (`app/pipeline/worker.py`)

```python
class ContentWorker:
    """Process articles, news, and podcasts."""

    def __init__(
        self,
        db: Session,
        strategy_registry: StrategyRegistry,
        llm_service: AnthropicSummarizationService,
    ):
        self.db = db
        self.registry = strategy_registry
        self.llm = llm_service

    def process_content(self, content_id: int, worker_id: str) -> bool:
        """
        Process single content item.

        Flow:
        1. Fetch from DB, convert to ContentData
        2. Route by content_type
        3. Update DB on completion
        """
        content = self.db.query(Content).get(content_id)
        if not content:
            return False

        content_data = ContentData.from_orm(content)

        try:
            if content_data.content_type in (ContentType.ARTICLE, ContentType.NEWS):
                result = self._process_article(content_data)
            elif content_data.content_type == ContentType.PODCAST:
                result = self._process_podcast(content_data)
            else:
                raise ValueError(f"Unknown type: {content_data.content_type}")

            # Update DB
            content.content_metadata = result.metadata.model_dump()
            content.title = result.title
            content.status = "completed"
            content.processed_at = datetime.utcnow()
            self.db.commit()

            return True

        except NonRetryableError as e:
            content.status = "failed"
            content.error_message = str(e)
            self.db.commit()
            return False
        except Exception as e:
            content.retry_count += 1
            if content.retry_count >= 3:
                content.status = "failed"
            else:
                content.status = "pending"
            content.error_message = str(e)
            self.db.commit()
            return False

    def _process_article(self, content: ContentData) -> ContentData:
        """
        Process article or news item.

        Steps:
        1. Resolve URL (handle news aggregates)
        2. Select processing strategy
        3. Download content
        4. Extract structured data
        5. Check for delegation (arXiv, PubMed)
        6. Skip if flagged (images)
        7. Summarize with LLM
        """
        url = self._resolve_article_url(content)

        # Get appropriate strategy
        strategy = self.registry.get_strategy(url)
        if not strategy:
            raise NonRetryableError(f"No strategy for: {url}")

        # Download
        raw_content = strategy.download_content(url)

        # Extract
        extracted = strategy.extract_data(raw_content, url)

        # Handle delegation
        if extracted.get("delegate_to"):
            return self._process_article(
                content.model_copy(update={"url": extracted["delegate_to"]})
            )

        # Skip processing for images
        if extracted.get("skip_processing"):
            content.metadata.content = extracted.get("content")
            return content

        # Prepare for LLM
        llm_input = strategy.prepare_for_llm(extracted)

        # Summarize
        summary = self.llm.summarize_content(
            content=llm_input["content"],
            content_type=content.content_type,
            title=llm_input.get("title"),
        )

        # Update metadata
        content.metadata.summary = summary
        content.metadata.content = extracted.get("content")
        content.metadata.word_count = len(extracted.get("content", "").split())
        content.title = summary.title or content.title

        return content
```

### 7.4 Sequential Task Processor

```python
class SequentialTaskProcessor:
    """Main task orchestrator - processes one task at a time."""

    def __init__(self, db: Session):
        self.db = db
        self.queue = QueueService(db)
        self.content_worker = ContentWorker(db, get_strategy_registry(), get_llm_service())
        self.running = True
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    def run(self) -> None:
        """Main processing loop."""
        while self.running:
            task = self.queue.dequeue()
            if not task:
                time.sleep(1)
                continue

            try:
                success = self.process_task(task)
                self.queue.complete_task(task["task_id"], success=success)
            except Exception as e:
                self.queue.complete_task(task["task_id"], success=False, error_message=str(e))

    def process_task(self, task: dict) -> bool:
        """Route task to appropriate handler."""
        handlers = {
            "SCRAPE": self._process_scrape_task,
            "PROCESS_CONTENT": self._process_content_task,
            "DOWNLOAD_AUDIO": self._process_download_task,
            "TRANSCRIBE": self._process_transcribe_task,
        }

        handler = handlers.get(task["task_type"])
        if not handler:
            raise ValueError(f"Unknown task type: {task['task_type']}")

        return handler(task)

    def _process_content_task(self, task: dict) -> bool:
        """Delegate to ContentWorker."""
        return self.content_worker.process_content(
            content_id=task["content_id"],
            worker_id=f"processor-{os.getpid()}",
        )

    def _handle_shutdown(self, signum, frame):
        """Graceful shutdown on SIGTERM."""
        self.running = False
```

---

## 8. Processing Strategies

### 8.1 Strategy Interface

```python
class UrlProcessorStrategy(ABC):
    """Base class for URL-specific content processors."""

    def __init__(self, http_client: RobustHttpClient):
        self.http = http_client

    def preprocess_url(self, url: str) -> str:
        """Normalize URL before processing. Override for URL transformations."""
        return url

    @abstractmethod
    def can_handle_url(self, url: str, response_headers: dict | None = None) -> bool:
        """Return True if this strategy can process the URL."""
        pass

    def download_content(self, url: str) -> Any:
        """
        Download raw content from URL.

        Returns: bytes (binary), str (text), or complex type
        """
        response = self.http.get(url)
        return response.content

    @abstractmethod
    def extract_data(self, content: Any, url: str) -> dict[str, Any]:
        """
        Extract structured data from downloaded content.

        Returns dict with keys:
        - content: str - Main text content
        - title: str | None
        - author: str | None
        - delegate_to: str | None - URL to re-process
        - skip_processing: bool - Skip LLM step
        - metadata: dict - Additional structured data
        """
        pass

    def prepare_for_llm(self, extracted_data: dict[str, Any]) -> dict[str, Any]:
        """
        Prepare extracted data for LLM summarization.

        Default: pass through content and title.
        Override for custom formatting.
        """
        return {
            "content": extracted_data.get("content", ""),
            "title": extracted_data.get("title"),
        }

    def extract_internal_urls(self, content: Any, original_url: str) -> list[str]:
        """Extract internal links for crawling. Override if needed."""
        return []
```

### 8.2 Strategy Implementations

#### HTML Strategy
```python
class HtmlProcessorStrategy(UrlProcessorStrategy):
    """Extract content from HTML pages using Crawl4AI."""

    def can_handle_url(self, url: str, headers: dict | None = None) -> bool:
        # Fallback strategy - handles any URL
        return True

    def download_content(self, url: str) -> str:
        """Download with Crawl4AI for JavaScript rendering."""
        async def _fetch():
            async with AsyncWebCrawler() as crawler:
                result = await crawler.arun(url)
                return result.markdown

        return asyncio.run(_fetch())

    def extract_data(self, content: str, url: str) -> dict:
        # Parse with BeautifulSoup for metadata
        soup = BeautifulSoup(content, "html.parser")

        return {
            "content": content,
            "title": self._extract_title(soup),
            "author": self._extract_author(soup),
            "metadata": {
                "content_type": "html",
                "final_url": url,
            },
        }
```

#### PDF Strategy
```python
class PdfProcessorStrategy(UrlProcessorStrategy):
    """Handle PDF documents."""

    def can_handle_url(self, url: str, headers: dict | None = None) -> bool:
        if url.lower().endswith(".pdf"):
            return True
        if headers and "application/pdf" in headers.get("content-type", ""):
            return True
        return False

    def download_content(self, url: str) -> bytes:
        response = self.http.get(url)
        return response.content

    def extract_data(self, content: bytes, url: str) -> dict:
        # Convert to base64 for LLM
        import base64
        pdf_b64 = base64.b64encode(content).decode("utf-8")

        return {
            "content": pdf_b64,
            "metadata": {"content_type": "pdf"},
        }

    def prepare_for_llm(self, extracted: dict) -> dict:
        # Format for multimodal LLM
        return {
            "content": f"[PDF Document Base64: {extracted['content'][:100]}...]",
            "is_pdf": True,
            "pdf_data": extracted["content"],
        }
```

#### YouTube Strategy
```python
class YouTubeProcessorStrategy(UrlProcessorStrategy):
    """Extract YouTube video metadata and transcripts."""

    YOUTUBE_PATTERNS = [
        r"youtube\.com/watch\?v=",
        r"youtu\.be/",
        r"youtube\.com/embed/",
    ]

    def can_handle_url(self, url: str, headers: dict | None = None) -> bool:
        return any(re.search(p, url) for p in self.YOUTUBE_PATTERNS)

    def extract_data(self, content: Any, url: str) -> dict:
        video_id = self._extract_video_id(url)

        # Get transcript via yt-dlp or YouTube API
        transcript = self._get_transcript(video_id)

        # Get video metadata
        metadata = self._get_video_metadata(video_id)

        return {
            "content": transcript or "",
            "title": metadata.get("title"),
            "metadata": {
                "video_id": video_id,
                "channel_name": metadata.get("channel"),
                "duration": metadata.get("duration"),
                "view_count": metadata.get("view_count"),
                "has_transcript": bool(transcript),
            },
            "skip_processing": not transcript,  # Skip if no transcript
        }
```

### 8.3 Strategy Registry

```python
class StrategyRegistry:
    """Registry for URL processing strategies with priority ordering."""

    def __init__(self):
        self._strategies: list[UrlProcessorStrategy] = []

    def register(self, strategy: UrlProcessorStrategy) -> None:
        """Add strategy to registry. Order matters - first match wins."""
        self._strategies.append(strategy)

    def get_strategy(
        self,
        url: str,
        headers: dict | None = None,
    ) -> UrlProcessorStrategy | None:
        """Find first strategy that can handle URL."""
        for strategy in self._strategies:
            if strategy.can_handle_url(url, headers):
                return strategy
        return None

    def list_strategies(self) -> list[str]:
        """List registered strategy names."""
        return [s.__class__.__name__ for s in self._strategies]

# Default registry setup
def get_strategy_registry() -> StrategyRegistry:
    registry = StrategyRegistry()
    http = RobustHttpClient()

    # Order matters: most specific first
    registry.register(HackerNewsProcessorStrategy(http))
    registry.register(ArxivProcessorStrategy(http))
    registry.register(PubMedProcessorStrategy(http))
    registry.register(YouTubeProcessorStrategy(http))
    registry.register(PdfProcessorStrategy(http))
    registry.register(ImageProcessorStrategy(http))
    registry.register(HtmlProcessorStrategy(http))  # Fallback

    return registry
```

---

## 9. Scrapers

### 9.1 Base Scraper

```python
class BaseScraper(ABC):
    """Abstract base class for content scrapers."""

    def __init__(self, name: str):
        self.name = name
        self.logger = get_logger(f"scraper.{name}")

    @abstractmethod
    def scrape(self) -> list[dict]:
        """
        Discover and return content items.

        Returns list of dicts with:
        - url: str (required)
        - title: str | None
        - content_type: str (article|podcast|news)
        - source: str
        - platform: str
        - metadata: dict
        """
        pass

    def run(self) -> int:
        """Execute scrape and save to database. Returns saved count."""
        items = self.scrape()
        saved = self._save_items(items)
        return saved

    def run_with_stats(self) -> ScraperStats:
        """Execute with detailed statistics."""
        start = datetime.utcnow()
        items = self.scrape()

        saved = 0
        duplicates = 0
        errors = 0

        for item in items:
            try:
                if self._save_item(item):
                    saved += 1
                else:
                    duplicates += 1
            except Exception:
                errors += 1

        return ScraperStats(
            name=self.name,
            items_found=len(items),
            items_saved=saved,
            duplicates=duplicates,
            errors=errors,
            duration=(datetime.utcnow() - start).total_seconds(),
        )

    def _save_item(self, item: dict) -> bool:
        """Save item to database, return True if new."""
        with get_db() as db:
            existing = db.query(Content).filter(
                Content.url == item["url"],
                Content.content_type == item["content_type"],
            ).first()

            if existing:
                return False

            content = Content(
                url=item["url"],
                title=item.get("title"),
                content_type=item["content_type"],
                source=item.get("source"),
                platform=item.get("platform"),
                content_metadata=item.get("metadata", {}),
                status="new",
            )
            db.add(content)
            db.commit()
            return True
```

### 9.2 Scraper Implementations

#### Hacker News Scraper
```python
class HackerNewsUnifiedScraper(BaseScraper):
    """Scrape top stories from Hacker News."""

    def __init__(self):
        super().__init__("hackernews")
        self.platform = "hackernews"

    def scrape(self) -> list[dict]:
        # Fetch top story IDs
        response = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json")
        story_ids = response.json()[:30]  # Top 30

        items = []
        for story_id in story_ids:
            story = self._fetch_story(story_id)
            if story and story.get("url"):
                items.append({
                    "url": story["url"],
                    "title": story.get("title"),
                    "content_type": "news",
                    "source": self._extract_domain(story["url"]),
                    "platform": self.platform,
                    "metadata": {
                        "aggregator": {
                            "name": "Hacker News",
                            "external_id": str(story_id),
                            "url": f"https://news.ycombinator.com/item?id={story_id}",
                        },
                    },
                })

        return items
```

#### Reddit Scraper
```python
class RedditUnifiedScraper(BaseScraper):
    """Scrape from configured subreddits using PRAW."""

    def __init__(self, subreddits: list[str]):
        super().__init__("reddit")
        self.reddit = praw.Reddit(
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret,
            user_agent="news_app/1.0",
        )
        self.subreddits = subreddits

    def scrape(self) -> list[dict]:
        items = []

        for subreddit_name in self.subreddits:
            subreddit = self.reddit.subreddit(subreddit_name)

            for post in subreddit.hot(limit=20):
                if post.is_self:
                    continue  # Skip self-posts

                items.append({
                    "url": post.url,
                    "title": post.title,
                    "content_type": "news",
                    "source": subreddit_name,
                    "platform": "reddit",
                    "metadata": {
                        "aggregator": {
                            "name": "Reddit",
                            "external_id": post.id,
                            "url": f"https://reddit.com{post.permalink}",
                            "metadata": {
                                "score": post.score,
                                "num_comments": post.num_comments,
                            },
                        },
                    },
                })

        return items
```

### 9.3 Scraper Runner

```python
class ScraperRunner:
    """Orchestrates all active scrapers."""

    def __init__(self, db: Session):
        self.db = db
        self.scrapers = self._build_scrapers()

    def _build_scrapers(self) -> list[BaseScraper]:
        """Initialize configured scrapers."""
        return [
            HackerNewsUnifiedScraper(),
            RedditUnifiedScraper(["MachineLearning", "programming"]),
            SubstackScraper(settings.substack_feeds),
            TechmemeScraper(),
            PodcastUnifiedScraper(settings.podcast_feeds),
            AtomScraper(settings.atom_feeds),
        ]

    def run_all(self) -> dict[str, int]:
        """Run all scrapers sequentially. Returns {name: count}."""
        results = {}
        for scraper in self.scrapers:
            try:
                count = scraper.run()
                results[scraper.name] = count
            except Exception as e:
                self.logger.error(f"Scraper {scraper.name} failed: {e}")
                results[scraper.name] = 0
        return results

    def run_all_with_stats(self) -> dict[str, ScraperStats]:
        """Run all scrapers with detailed statistics."""
        results = {}
        for scraper in self.scrapers:
            try:
                stats = scraper.run_with_stats()
                results[scraper.name] = stats
            except Exception as e:
                self.logger.error(f"Scraper {scraper.name} failed: {e}")
        return results

    def run_scraper(self, name: str) -> int | None:
        """Run single scraper by name."""
        for scraper in self.scrapers:
            if scraper.name == name:
                return scraper.run()
        return None
```

---

## 10. iOS Client Architecture

### 10.1 SwiftUI App Structure

```
newsly/
├── newslyApp.swift              # App entry + auth gate
├── ContentView.swift            # Root navigation
│
├── Models/
│   ├── User.swift               # User model
│   ├── ContentSummary.swift     # List item model
│   ├── ContentDetail.swift      # Detail model
│   ├── StructuredSummary.swift  # Summary model
│   └── ContentType.swift        # Type enum
│
├── ViewModels/
│   ├── AuthenticationViewModel.swift  # Auth state
│   ├── ContentListViewModel.swift     # Feed logic
│   └── ContentDetailViewModel.swift   # Detail logic
│
├── Views/
│   ├── AuthenticationView.swift       # Login UI
│   ├── ShortFormView.swift           # News (swipeable)
│   ├── LongFormView.swift            # Articles (paged)
│   ├── FavoritesView.swift           # Favorites
│   └── Components/
│       ├── SwipeableCard.swift       # Swipe gesture card
│       ├── PagedCardView.swift       # Pageable card
│       └── ...
│
└── Services/
    ├── APIClient.swift               # HTTP + JWT
    ├── AuthenticationService.swift   # Apple Sign In
    ├── KeychainManager.swift         # Token storage
    └── ContentService.swift          # Content API
```

### 10.2 API Client

```swift
class APIClient {
    static let shared = APIClient()

    private var accessToken: String?
    private var refreshToken: String?

    func request<T: Decodable>(
        _ endpoint: APIEndpoint,
        responseType: T.Type
    ) async throws -> T {
        var request = URLRequest(url: endpoint.url)
        request.httpMethod = endpoint.method.rawValue

        // Add auth header
        if let token = accessToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        let (data, response) = try await URLSession.shared.data(for: request)

        // Handle 401 - refresh token
        if let httpResponse = response as? HTTPURLResponse,
           httpResponse.statusCode == 401 {
            try await refreshAccessToken()
            return try await self.request(endpoint, responseType: responseType)
        }

        return try JSONDecoder().decode(T.self, from: data)
    }

    private func refreshAccessToken() async throws {
        guard let refresh = refreshToken else {
            throw AuthError.noRefreshToken
        }

        let response = try await request(
            .refreshToken(refresh),
            responseType: TokenResponse.self
        )

        self.accessToken = response.accessToken
        self.refreshToken = response.refreshToken

        // Persist to Keychain
        try KeychainManager.shared.save(accessToken: response.accessToken)
        try KeychainManager.shared.save(refreshToken: response.refreshToken)
    }
}
```

### 10.3 Authentication Flow

```swift
class AuthenticationService {
    static let shared = AuthenticationService()

    func signInWithApple() async throws -> User {
        // 1. Request Apple Sign In
        let request = ASAuthorizationAppleIDProvider().createRequest()
        request.requestedScopes = [.email, .fullName]

        let controller = ASAuthorizationController(authorizationRequests: [request])
        let result = try await controller.performRequests()

        guard let credential = result.credential as? ASAuthorizationAppleIDCredential,
              let identityToken = credential.identityToken,
              let tokenString = String(data: identityToken, encoding: .utf8) else {
            throw AuthError.invalidCredential
        }

        // 2. Send to backend
        let response = try await APIClient.shared.request(
            .appleSignIn(
                idToken: tokenString,
                email: credential.email,
                fullName: credential.fullName?.formatted()
            ),
            responseType: TokenResponse.self
        )

        // 3. Store tokens
        try KeychainManager.shared.save(accessToken: response.accessToken)
        try KeychainManager.shared.save(refreshToken: response.refreshToken)

        return response.user
    }
}
```

### 10.4 Content ViewModels

```swift
@MainActor
class ContentListViewModel: ObservableObject {
    @Published var contents: [ContentSummary] = []
    @Published var isLoading = false
    @Published var error: Error?

    private var nextCursor: String?
    private var hasMore = true

    func loadContent(
        contentTypes: [ContentType] = [],
        readFilter: ReadFilter = .all
    ) async {
        guard !isLoading, hasMore else { return }
        isLoading = true

        do {
            let response = try await ContentService.shared.listContent(
                contentTypes: contentTypes,
                readFilter: readFilter,
                cursor: nextCursor
            )

            contents.append(contentsOf: response.contents)
            nextCursor = response.nextCursor
            hasMore = response.hasMore
        } catch {
            self.error = error
        }

        isLoading = false
    }

    func markAsRead(_ content: ContentSummary) async {
        try? await ContentService.shared.markAsRead(content.id)

        // Update local state
        if let index = contents.firstIndex(where: { $0.id == content.id }) {
            contents[index].isRead = true
        }
    }

    func toggleFavorite(_ content: ContentSummary) async {
        let response = try? await ContentService.shared.toggleFavorite(content.id)

        if let index = contents.firstIndex(where: { $0.id == content.id }) {
            contents[index].isFavorited = response?.isFavorited ?? !contents[index].isFavorited
        }
    }
}
```

---

## 11. Architectural Patterns

### 11.1 Dependency Injection

FastAPI's `Depends()` system provides dependency injection throughout the codebase.

```python
# Database session injection
@router.get("/")
async def list_content(
    db: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> ContentListResponse:
    ...

# Annotated pattern for cleaner signatures
from typing import Annotated

DbSession = Annotated[Session, Depends(get_db_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]

@router.get("/")
async def list_content(db: DbSession, user: CurrentUser) -> ContentListResponse:
    ...
```

### 11.2 RORO Pattern (Receive Object, Return Object)

Functions receive structured input and return structured output.

```python
# Instead of:
def process(content_id: int, title: str, url: str, ...) -> tuple[bool, str]:
    ...

# Use:
def process(content: ContentData) -> ProcessingResult:
    ...
```

### 11.3 Strategy Pattern

Content processing uses the strategy pattern for extensibility.

```python
# Adding new content type:
class TwitterProcessorStrategy(UrlProcessorStrategy):
    def can_handle_url(self, url: str, headers: dict | None) -> bool:
        return "twitter.com" in url or "x.com" in url

    def extract_data(self, content: Any, url: str) -> dict:
        # Twitter-specific extraction
        ...

# Register with registry
registry.register(TwitterProcessorStrategy(http_client))
```

### 11.4 Repository Pattern

Services abstract database operations from endpoints.

```python
# app/services/favorites.py - Repository layer
def toggle_favorite(db: Session, content_id: int, user_id: int) -> tuple[bool, ...]:
    ...

# app/routers/api/favorites.py - API layer
@router.post("/{content_id}/favorites/toggle")
async def toggle_favorite_endpoint(
    content_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> dict:
    is_favorited, _ = toggle_favorite(db, content_id, user.id)
    return {"is_favorited": is_favorited}
```

### 11.5 Context Managers for Resource Management

```python
# Database sessions
with get_db() as db:
    # Auto commit on success, rollback on error

# Content checkout
with checkout_manager.checkout_content(worker_id) as items:
    # Auto release on exit

# Event tracking
with track_event(db, "scraper_run", "hackernews") as event:
    # Auto log start/end/duration
```

### 11.6 Task Queue Pattern

Database-backed queue with row-level locking for distributed safety.

```python
# Enqueue
task_id = queue.enqueue("PROCESS_CONTENT", content_id=123)

# Dequeue with lock
task = queue.dequeue(task_type="PROCESS_CONTENT", worker_id="worker-1")
# Row locked with FOR UPDATE SKIP LOCKED

# Complete
queue.complete_task(task_id, success=True)
```

---

## 12. Data Flow Diagrams

### 12.1 Authentication Flow

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   iOS App    │    │    Apple     │    │   FastAPI    │    │   Database   │
│              │    │    Auth      │    │   Backend    │    │              │
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘    └──────┬───────┘
       │                   │                   │                   │
       │ 1. Request        │                   │                   │
       │    Sign In        │                   │                   │
       │──────────────────▶│                   │                   │
       │                   │                   │                   │
       │ 2. Identity       │                   │                   │
       │    Token          │                   │                   │
       │◀──────────────────│                   │                   │
       │                   │                   │                   │
       │ 3. POST /auth/apple                   │                   │
       │   {id_token, email, name}             │                   │
       │──────────────────────────────────────▶│                   │
       │                   │                   │                   │
       │                   │                   │ 4. Find/Create    │
       │                   │                   │    User           │
       │                   │                   │──────────────────▶│
       │                   │                   │                   │
       │                   │                   │◀──────────────────│
       │                   │                   │                   │
       │ 5. {access_token, refresh_token, user}│                   │
       │◀──────────────────────────────────────│                   │
       │                   │                   │                   │
       │ 6. Store in       │                   │                   │
       │    Keychain       │                   │                   │
       │                   │                   │                   │
```

### 12.2 Content Processing Flow

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Scraper    │    │  Database   │    │  Task       │    │  Worker     │
│             │    │             │    │  Processor  │    │             │
└──────┬──────┘    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘
       │                  │                  │                  │
       │ 1. Scrape        │                  │                  │
       │    sources       │                  │                  │
       │                  │                  │                  │
       │ 2. Insert        │                  │                  │
       │    Content       │                  │                  │
       │    (status:new)  │                  │                  │
       │─────────────────▶│                  │                  │
       │                  │                  │                  │
       │                  │ 3. Poll for     │                  │
       │                  │    new tasks     │                  │
       │                  │◀─────────────────│                  │
       │                  │                  │                  │
       │                  │ 4. Return task   │                  │
       │                  │    (with lock)   │                  │
       │                  │─────────────────▶│                  │
       │                  │                  │                  │
       │                  │                  │ 5. Dispatch      │
       │                  │                  │    to worker     │
       │                  │                  │─────────────────▶│
       │                  │                  │                  │
       │                  │                  │                  │ 6. Select
       │                  │                  │                  │    strategy
       │                  │                  │                  │
       │                  │                  │                  │ 7. Download
       │                  │                  │                  │    content
       │                  │                  │                  │
       │                  │                  │                  │ 8. Extract
       │                  │                  │                  │    data
       │                  │                  │                  │
       │                  │                  │                  │ 9. LLM
       │                  │                  │                  │    summarize
       │                  │                  │                  │
       │                  │ 10. Update       │                  │
       │                  │     Content      │                  │
       │                  │  (status:done)   │                  │
       │                  │◀─────────────────────────────────────│
       │                  │                  │                  │
```

### 12.3 API Request Flow

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  iOS App    │    │  FastAPI    │    │  Service    │    │  Database   │
│             │    │  Router     │    │  Layer      │    │             │
└──────┬──────┘    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘
       │                  │                  │                  │
       │ 1. GET /api/content?type=article    │                  │
       │   Authorization: Bearer <token>     │                  │
       │─────────────────▶│                  │                  │
       │                  │                  │                  │
       │                  │ 2. Validate JWT  │                  │
       │                  │    (deps.py)     │                  │
       │                  │                  │                  │
       │                  │ 3. Get user      │                  │
       │                  │────────────────────────────────────▶│
       │                  │                  │                  │
       │                  │◀────────────────────────────────────│
       │                  │                  │                  │
       │                  │ 4. Query content │                  │
       │                  │    with filters  │                  │
       │                  │────────────────────────────────────▶│
       │                  │                  │                  │
       │                  │◀────────────────────────────────────│
       │                  │                  │                  │
       │                  │ 5. Get read IDs  │                  │
       │                  │─────────────────▶│                  │
       │                  │                  │─────────────────▶│
       │                  │                  │◀─────────────────│
       │                  │◀─────────────────│                  │
       │                  │                  │                  │
       │                  │ 6. Get favorites │                  │
       │                  │─────────────────▶│                  │
       │                  │                  │─────────────────▶│
       │                  │                  │◀─────────────────│
       │                  │◀─────────────────│                  │
       │                  │                  │                  │
       │ 7. ContentListResponse              │                  │
       │◀─────────────────│                  │                  │
       │                  │                  │                  │
```

---

## 13. Security Architecture

### 13.1 Authentication Model

| Component | Method | Storage |
|-----------|--------|---------|
| iOS App | JWT Bearer tokens | iOS Keychain |
| Web Admin | Session cookies | In-memory (server) |
| API Requests | Authorization header | N/A |

### 13.2 Token Lifecycle

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           TOKEN LIFECYCLE                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐                    ┌──────────────┐                       │
│  │ Access Token │                    │Refresh Token │                       │
│  │  (30 min)    │                    │  (90 days)   │                       │
│  └──────┬───────┘                    └──────┬───────┘                       │
│         │                                   │                                │
│         │ Used for API requests             │ Used to get new tokens        │
│         │                                   │                                │
│         ▼                                   ▼                                │
│  ┌──────────────┐                    ┌──────────────┐                       │
│  │ API Call     │                    │ /auth/refresh│                       │
│  │ with Bearer  │                    │              │                       │
│  └──────┬───────┘                    └──────┬───────┘                       │
│         │                                   │                                │
│         ▼                                   ▼                                │
│  ┌──────────────┐                    ┌──────────────┐                       │
│  │ 401 if       │                    │ New tokens   │                       │
│  │ expired      │────────────────────│ (rotation)   │                       │
│  └──────────────┘                    └──────────────┘                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 13.3 Data Isolation

All user-specific data is isolated by `user_id`:

- `content_read_status.user_id`
- `content_favorites.user_id`
- `content_unlikes.user_id`

Queries always filter by authenticated user's ID.

### 13.4 Security Warnings (MVP)

| Issue | Location | Risk | Remediation |
|-------|----------|------|-------------|
| Apple token verification disabled | `app/core/security.py:106` | High | Implement full verification with Apple public keys |
| Admin sessions in-memory | `app/routers/auth.py:31` | Medium | Move to Redis or database with TTL |
| No rate limiting | All endpoints | Medium | Add per-IP/per-user rate limits |
| CORS allows all origins | `app/main.py` | Low | Restrict to known domains |

---

## Appendix A: Key File Reference

| File | Purpose |
|------|---------|
| `app/main.py` | FastAPI app entry, middleware, router mounting |
| `app/core/db.py` | SQLAlchemy engine, session management |
| `app/core/settings.py` | Pydantic configuration from .env |
| `app/core/security.py` | JWT utilities, Apple token validation |
| `app/core/deps.py` | FastAPI auth dependencies |
| `app/models/schema.py` | SQLAlchemy ORM models |
| `app/models/metadata.py` | Pydantic content metadata schemas |
| `app/routers/api/*.py` | REST API endpoints |
| `app/services/favorites.py` | Favorites operations |
| `app/services/read_status.py` | Read tracking operations |
| `app/services/queue.py` | Task queue service |
| `app/pipeline/worker.py` | Content processing worker |
| `app/pipeline/checkout.py` | Distributed checkout manager |
| `app/processing_strategies/registry.py` | Strategy pattern registry |
| `app/scraping/runner.py` | Scraper orchestrator |

---

## Appendix B: Type Hierarchy

```
ContentType (Enum)
├── ARTICLE
├── PODCAST
└── NEWS

ContentStatus (Enum)
├── NEW
├── PENDING
├── PROCESSING
├── COMPLETED
├── FAILED
└── SKIPPED

ContentClassification (Enum)
├── TO_READ
└── SKIP

Metadata Models
├── ArticleMetadata
│   └── summary: StructuredSummary
├── PodcastMetadata
│   └── summary: StructuredSummary
└── NewsMetadata
    ├── article: NewsArticleMetadata
    ├── aggregator: NewsAggregatorMetadata
    └── summary: NewsSummary

StructuredSummary
├── bullet_points: list[SummaryBulletPoint]
├── quotes: list[ContentQuote]
├── topics: list[str]
├── questions: list[str]
└── counter_arguments: list[str]

ContentData (Unified Wrapper)
├── content_type: ContentType
├── status: ContentStatus
└── metadata: ArticleMetadata | PodcastMetadata | NewsMetadata
```

---

---

## 14. Deep Dive Chat System

### 14.1 Overview

The Deep Dive Chat feature enables conversational AI interactions with article content using pydantic-ai agents. Users can:
- Start article-focused chats from content detail view
- Start topic-focused chats from summary topics
- Create ad-hoc chats without article context
- Use Exa web search for additional context

### 14.2 Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          DEEP DIVE CHAT SYSTEM                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────────────┐   │
│  │   iOS App    │────│  Chat API    │────│    pydantic-ai Agent        │   │
│  │   (SwiftUI)  │    │  (FastAPI)   │    │  (chat_agent.py)            │   │
│  └──────────────┘    └──────────────┘    └──────────────────────────────┘   │
│         │                   │                          │                     │
│         │            ┌──────┴──────┐          ┌───────┴───────┐             │
│         │            │             │          │               │             │
│    ┌────┴────┐  ┌────┴────┐  ┌─────┴─────┐   │    ┌─────────┴─────────┐   │
│    │ Chats   │  │ Chat    │  │ Chat      │   │    │   Exa Web Search  │   │
│    │ Tab     │  │ Sessions│  │ Messages  │   │    │   (Tool)          │   │
│    └─────────┘  └─────────┘  └───────────┘   │    └───────────────────┘   │
│                                               │                             │
│                                   ┌───────────┴───────────┐                │
│                                   │                       │                │
│                             ┌─────┴─────┐          ┌──────┴──────┐        │
│                             │  OpenAI   │          │  Anthropic  │        │
│                             │  gpt-5.1  │          │  Claude     │        │
│                             └───────────┘          └─────────────┘        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 14.3 Database Schema

```python
class ChatSession(Base):
    """Deep Dive Chat session."""
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(index=True)
    content_id: Mapped[int | None] = mapped_column(index=True)  # Article reference
    title: Mapped[str | None] = mapped_column(String(500))
    session_type: Mapped[str | None] = mapped_column(String(50))  # article_brain, topic, ad_hoc
    topic: Mapped[str | None] = mapped_column(String(500))
    llm_model: Mapped[str] = mapped_column(String(100), default="openai:gpt-5.1")
    llm_provider: Mapped[str] = mapped_column(String(50), default="openai")
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime | None]
    last_message_at: Mapped[datetime | None]
    is_archived: Mapped[bool] = mapped_column(default=False)

class ChatMessage(Base):
    """Message history using pydantic-ai format."""
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(index=True)
    message_list: Mapped[str]  # JSON from ModelMessagesTypeAdapter
    created_at: Mapped[datetime]
```

### 14.4 Chat Agent (`app/services/chat_agent.py`)

```python
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessagesTypeAdapter

@dataclass
class ChatDeps:
    """Dependencies injected into chat agent."""
    db: Session
    content_id: int | None
    article_context: str | None

def get_chat_agent(model_spec: str) -> Agent[ChatDeps, str]:
    """Get or create a chat agent for the given model spec."""
    agent = Agent(
        model_spec,  # e.g., "openai:gpt-5.1"
        deps_type=ChatDeps,
        output_type=str,
        system_prompt="You are a deep-dive assistant...",
    )

    @agent.system_prompt
    async def add_article_context(ctx: RunContext[ChatDeps]) -> str:
        """Inject article context into system prompt."""
        if ctx.deps.article_context:
            return f"Article Context:\n{ctx.deps.article_context}"
        return ""

    @agent.tool
    async def exa_web_search(
        ctx: RunContext[ChatDeps],
        query: str,
        num_results: int = 5,
    ) -> list[ExaSearchResultModel]:
        """Search the web using Exa for additional context."""
        results = exa_search(query, num_results)
        return [ExaSearchResultModel(...) for r in results]

    return agent

async def run_chat_stream(
    db: Session,
    session: ChatSession,
    user_prompt: str,
) -> AsyncIterator[str]:
    """Run a chat turn with streaming output."""
    # Load message history
    history = load_message_history(db, session.id)

    # Build context
    deps = ChatDeps(
        db=db,
        content_id=session.content_id,
        article_context=build_article_context(db, session.content_id),
    )

    # Get agent
    agent = get_chat_agent(session.llm_model)

    # Stream response
    async with agent.run_stream(user_prompt, message_history=history, deps=deps) as result:
        async for chunk in result.stream_text():
            yield chunk

    # Persist messages
    save_message_history(db, session.id, result.all_messages())

    # Update session
    session.last_message_at = datetime.utcnow()
    db.commit()
```

### 14.5 API Endpoints (`app/routers/api/chat.py`)

```python
router = APIRouter(prefix="/chat", tags=["chat"])

@router.get("/sessions", response_model=list[ChatSessionSummaryResponse])
async def list_sessions(
    db: Session,
    current_user: User,
    content_id: int | None = None,
    limit: int = 50,
) -> list[ChatSessionSummaryResponse]:
    """List chat sessions for current user."""

@router.post("/sessions", response_model=CreateChatSessionResponse)
async def create_session(
    request: CreateChatSessionRequest,
    db: Session,
    current_user: User,
) -> CreateChatSessionResponse:
    """Create a new chat session."""

@router.get("/sessions/{session_id}", response_model=ChatSessionDetailResponse)
async def get_session(
    session_id: int,
    db: Session,
    current_user: User,
) -> ChatSessionDetailResponse:
    """Get session details with message history."""

@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: int,
    request: SendChatMessageRequest,
    db: Session,
    current_user: User,
) -> StreamingResponse:
    """Send message and stream response as NDJSON."""
    async def generate():
        # Yield user message
        yield json.dumps(user_msg.model_dump(mode="json")) + "\n"

        # Stream assistant response
        async for chunk in run_chat_stream(db, session, request.message):
            accumulated_text += chunk
            yield json.dumps(partial_msg.model_dump(mode="json")) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")
```

### 14.6 iOS Client

**Models:**
- `ChatSessionSummary` - Session list item
- `ChatMessage` - Individual message
- `ChatSessionDetail` - Session with messages
- `ChatModelProvider` - LLM provider enum

**Services:**
- `ChatService` - API client with NDJSON streaming via `APIClient.streamNDJSON()`

**ViewModels:**
- `ChatSessionsViewModel` - Session list management
- `ChatSessionViewModel` - Chat conversation with streaming

**Views:**
- `ChatSessionsView` - Chats tab (3rd position)
- `ChatSessionView` - Chat UI with message bubbles

**Entry Points:**
- Brain button in `ContentDetailView` - Start article chat
- Topic long-press in `StructuredSummaryView` - Start topic chat
- Plus button in `ChatSessionsView` - Start ad-hoc chat

### 14.7 Model Resolution

```python
DEFAULT_MODELS = {
    "openai": "openai:gpt-5.1",
    "anthropic": "anthropic:claude-3-5-sonnet-latest",
    "google": "google-gla:gemini-2.5-flash",
}

def resolve_model(
    provider: str | None = None,
    model_hint: str | None = None,
) -> tuple[str, str]:
    """Resolve provider and model hint to pydantic-ai model string.

    Returns: (provider_name, full_model_spec)
    """
    provider = provider or "openai"
    if model_hint:
        return provider, f"{provider}:{model_hint}"
    return provider, DEFAULT_MODELS.get(provider, DEFAULT_MODELS["openai"])
```

---

*Generated from codebase analysis, November 2025*

---

## Appendix A: Complete Project Structure

### Python Backend (`app/`)
```
app/
├── core/                          # Core infrastructure
│   ├── db.py                     # SQLAlchemy engine, sessions, init_db()
│   ├── settings.py               # Pydantic v2 settings from .env
│   ├── logging.py                # Root logger setup
│   ├── security.py               # JWT utils, Apple token validation
│   └── deps.py                   # FastAPI auth dependencies
│
├── models/                        # Database & domain models
│   ├── schema.py                 # SQLAlchemy models (Content, ProcessingTask, etc.)
│   ├── user.py                   # User model + auth Pydantic schemas
│   ├── metadata.py               # Unified Pydantic metadata models
│   ├── pagination.py             # Pagination models
│   └── scraper_runs.py           # ScraperStats dataclass
│
├── routers/                       # FastAPI endpoints
│   ├── auth.py                   # Apple Sign In, refresh, admin login/logout
│   ├── content.py                # Web UI routes (/, /content/{id}, /favorites)
│   ├── admin.py                  # Admin dashboard (/admin/)
│   ├── logs.py                   # Log viewing & error analysis
│   ├── api_content.py            # API backward compatibility layer
│   └── api/                      # Refactored API routes
│       ├── __init__.py           # Combined router
│       ├── models.py             # API Pydantic schemas
│       ├── content_list.py       # GET /, /search, /unread-counts
│       ├── content_detail.py     # GET /{id}, /chatgpt-url
│       ├── read_status.py        # POST /mark-read, /bulk-mark-read
│       ├── favorites.py          # POST /favorites/toggle, GET /favorites
│       ├── content_actions.py    # POST /convert (news→article)
│       └── chat.py               # Deep dive chat sessions & messages
│
├── services/                      # Business logic
│   ├── anthropic_llm.py          # Anthropic Claude integration
│   ├── openai_llm.py             # OpenAI GPT integration (summarization)
│   ├── google_flash.py           # Google Gemini Flash integration
│   ├── llm_prompts.py            # LLM prompt templates
│   ├── event_logger.py           # EventLog service
│   ├── favorites.py              # User favorites operations
│   ├── read_status.py            # User read status tracking
│   ├── queue.py                  # Queue service & stats
│   ├── http.py                   # HTTP client helpers
│   ├── whisper_local.py          # Local Whisper transcription
│   ├── exa_client.py             # Exa web search integration
│   ├── chat_agent.py             # pydantic-ai Agent for Deep Dive Chat
│   └── tweet_suggestions.py      # Tweet generation from content
│
├── pipeline/                      # Task processing
│   ├── sequential_task_processor.py  # Main orchestrator
│   ├── worker.py                 # ContentWorker (articles/news)
│   ├── podcast_workers.py        # PodcastDownloadWorker, TranscribeWorker
│   └── checkout.py               # Content checkout mechanism
│
├── scraping/                      # Content scrapers
│   ├── runner.py                 # Scraper orchestrator
│   ├── base.py                   # Base scraper class
│   ├── substack_unified.py       # Substack scraper
│   ├── podcast_unified.py        # Podcast RSS/download
│   ├── hackernews_unified.py     # Hacker News
│   ├── reddit_unified.py         # Reddit (via PRAW)
│   ├── twitter_unified.py        # Twitter/X
│   ├── techmeme_unified.py       # Techmeme aggregator
│   ├── youtube_unified.py        # YouTube videos
│   └── atom_unified.py           # Generic Atom/RSS feeds
│
├── processing_strategies/         # Content-type processors
│   ├── base_strategy.py          # Base strategy interface
│   ├── registry.py               # Strategy registry
│   ├── html_strategy.py          # HTML extraction (crawl4ai)
│   ├── pdf_strategy.py           # PDF extraction
│   ├── arxiv_strategy.py         # arXiv papers
│   ├── pubmed_strategy.py        # PubMed articles
│   ├── hackernews_strategy.py    # HN comment extraction
│   ├── youtube_strategy.py       # YouTube transcript/metadata
│   └── image_strategy.py         # Image content
│
├── http_client/
│   └── robust_http_client.py     # Resilient HTTP with retries
│
├── utils/
│   ├── error_logger.py           # JSONL error logging
│   ├── pagination.py             # Cursor pagination utils
│   ├── paths.py                  # Path utilities
│   └── json_repair.py            # JSON repair utilities
│
├── domain/
│   └── converters.py             # ORM→Pydantic converters
│
├── templates.py                   # Jinja2 template config
├── constants.py                   # App-wide constants
└── main.py                        # FastAPI app entry point
```

### iOS Client (`client/newsly/newsly/`)
```
client/newsly/newsly/
├── newslyApp.swift               # App entry, auth gate
├── ContentView.swift             # Main app container
├── Info.plist                    # App capabilities
├── newsly.entitlements           # Sign in with Apple
│
├── Models/
│   ├── User.swift                # User model
│   ├── ContentSummary.swift      # List view model
│   ├── ContentDetail.swift       # Detail view model
│   ├── ContentListResponse.swift # API response wrapper
│   ├── ContentType.swift         # article/podcast/news enum
│   ├── ContentStatus.swift       # processing status enum
│   ├── StructuredSummary.swift   # Structured summary model
│   ├── ArticleMetadata.swift     # Article-specific metadata
│   ├── PodcastMetadata.swift     # Podcast-specific metadata
│   ├── NewsMetadata.swift        # News-specific metadata
│   ├── NewsGroup.swift           # Grouped news model
│   ├── AnyCodable.swift          # JSON flexibility helper
│   ├── ChatSessionSummary.swift  # Chat session list model
│   ├── ChatMessage.swift         # Individual chat message
│   ├── ChatSessionDetail.swift   # Chat session with messages
│   └── ChatModelProvider.swift   # LLM provider enum
│
├── ViewModels/
│   ├── AuthenticationViewModel.swift     # Apple Sign In state
│   ├── ContentListViewModel.swift        # Main feed logic
│   ├── ContentDetailViewModel.swift      # Detail view logic
│   ├── ArticleDetailViewModel.swift      # Article-specific
│   ├── PodcastDetailViewModel.swift      # Podcast-specific
│   ├── NewsGroupViewModel.swift          # News grouping
│   ├── SearchViewModel.swift             # Search functionality
│   ├── ChatSessionsViewModel.swift       # Chat sessions list
│   └── ChatSessionViewModel.swift        # Individual chat session
│
├── Views/
│   ├── AuthenticationView.swift          # Login screen
│   ├── ContentListView.swift             # Main feed (deprecated)
│   ├── ContentDetailView.swift           # Detail screen
│   ├── ShortFormView.swift               # News feed (swipeable cards)
│   ├── LongFormView.swift                # Articles/podcasts (paged)
│   ├── FavoritesView.swift               # Favorites screen
│   ├── RecentlyReadView.swift            # Read history
│   ├── SearchView.swift                  # Search interface
│   ├── SettingsView.swift                # Settings & logout
│   ├── DebugMenuView.swift               # Debug tools
│   ├── ChatSessionsView.swift            # Chat sessions list (Chats tab)
│   ├── ChatSessionView.swift             # Individual chat conversation
│   └── Components/
│       ├── SwipeableCard.swift           # Swipeable news card
│       ├── PagedCardView.swift           # Pageable article card
│       ├── CardStackView.swift           # Card stack container
│       ├── ContentCard.swift             # Generic content card
│       ├── NewsGroupCard.swift           # Grouped news display
│       ├── NewsDigestDetailView.swift    # News detail modal
│       ├── StructuredSummaryView.swift   # Summary display
│       ├── FilterBar.swift               # Filter controls
│       ├── FilterSheet.swift             # Filter modal
│       ├── ContentTypeBadge.swift        # Type indicator
│       ├── PlatformIcon.swift            # Source icon
│       ├── PlaceholderCard.swift         # Loading state
│       ├── LoadingView.swift             # Loading spinner
│       ├── ErrorView.swift               # Error display
│       └── ToastView.swift               # Toast notifications
│
└── Services/
    ├── APIClient.swift               # HTTP client, JWT auto-refresh
    ├── APIEndpoints.swift            # Endpoint definitions
    ├── AuthenticationService.swift   # Apple Sign In integration
    ├── KeychainManager.swift         # Secure token storage
    ├── ContentService.swift          # Content API calls
    ├── AppSettings.swift             # User preferences
    ├── ChatGPTDeepLinkService.swift  # ChatGPT integration
    ├── ToastService.swift            # Toast management
    ├── UnreadCountService.swift      # Badge counts
    ├── ChatService.swift             # Deep Dive Chat API client
    ├── TwitterShareService.swift     # Twitter share deep links
    └── VoiceDictationService.swift   # Voice input for tweets
```

### Project Root
```
├── templates/         # Primary Jinja templates (admin dashboard, logs, lists)
├── static/            # Tailwind sources and compiled CSS
│   └── css/
│       ├── styles.css  # Source Tailwind CSS
│       └── app.css     # Compiled output
├── scripts/           # Operational scripts
├── alembic/           # Database migrations
├── logs/              # JSONL and service logs (host-mounted)
├── docs/              # Documentation
├── pyproject.toml     # Python dependencies (uv)
├── uv.lock            # Lock file
├── alembic.ini        # Alembic configuration
└── docker-compose.yml # Container orchestration
```

---

## Appendix B: Environment Variables

All variables loaded via `app/core/settings.py` (Pydantic v2 BaseSettings).

### Required
```bash
# Database
DATABASE_URL="sqlite:///./news_app.db"  # or postgresql://user:pass@host/db

# Authentication
JWT_SECRET_KEY=<generate: python -c "import secrets; print(secrets.token_urlsafe(32))">
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=90
ADMIN_PASSWORD=<your-secure-admin-password>
```

### Optional - LLM Services
```bash
ANTHROPIC_API_KEY=<anthropic-api-key>
OPENAI_API_KEY=<openai-api-key>
GOOGLE_API_KEY=<google-api-key>
EXA_API_KEY=<exa-api-key>  # For Deep Dive Chat web search
```

### Optional - Processing
```bash
WHISPER_MODEL_SIZE=base    # tiny, base, small, medium, large
WHISPER_DEVICE=auto        # cpu, cuda, mps, auto
MAX_CONTENT_LENGTH=100000
```

### Optional - Reddit
```bash
REDDIT_CLIENT_ID=<reddit-client-id>
REDDIT_CLIENT_SECRET=<reddit-client-secret>
REDDIT_USER_AGENT="newsly/1.0"
```

---

## Appendix C: Operational Scripts

### Start Scripts
| Script | Description |
|--------|-------------|
| `scripts/start_server.sh` | Run migrations + uvicorn (port 8000) |
| `scripts/start_workers.sh` | Run migrations + Playwright + workers |
| `scripts/start_scrapers.sh` | Run scrapers with stats |

### Worker Entry Points
| Script | Description |
|--------|-------------|
| `scripts/run_workers.py` | Sequential task processor |
| `scripts/run_scrapers.py` | Scraper runner |

### Database Management
| Script | Description |
|--------|-------------|
| `scripts/init_database.py` | Initialize database schema |
| `scripts/dump_database.py` | Export database to JSON |
| `scripts/dump_system_stats.py` | System statistics report |
| `scripts/backup_database.sh` | Backup SQLite database |
| `scripts/sync_db_from_remote.sh` | Sync database from remote |

### Content Management
| Script | Description |
|--------|-------------|
| `scripts/reset_content_processing.py` | Reset content processing status |
| `scripts/reset_errored_content.py` | Reset failed content for retry |
| `scripts/enqueue_past_day_summarization.py` | Re-queue recent content |
| `scripts/resummarize_podcasts.py` | Re-summarize podcasts |
| `scripts/retranscribe_podcasts.py` | Re-transcribe podcast audio |
| `scripts/generate_test_data.py` | Create test content |

### Diagnostics
| Script | Description |
|--------|-------------|
| `scripts/analyze_errors.py` | Analyze error logs |
| `scripts/audit_feeds.py` | Audit feed configurations |
| `scripts/diagnose_youtube.py` | Debug YouTube scraper |
| `scripts/compare_llm_summarization.py` | Compare LLM outputs |
| `scripts/test_auth_flow.sh` | Test authentication flow |

### Environment
| Script | Description |
|--------|-------------|
| `scripts/setup_uv_env.sh` | Setup uv environment |
| `scripts/install_uv_env.sh` | Install dependencies via uv |
| `scripts/clean_env.sh` | Clean virtual environment |

### Deployment
| Script | Description |
|--------|-------------|
| `scripts/deploy/push_app.sh` | Deploy to remote server |
| `scripts/deploy/push_envs.sh` | Deploy environment variables |

---

## Appendix D: Quick Links (Fast Onboarding)

### Application Entry
- `app/main.py` — FastAPI app entry, router mounting, CORS, static files

### Core Infrastructure
- `app/core/settings.py` — Pydantic v2 settings from `.env`
- `app/core/logging.py` — Root logger configuration
- `app/core/db.py` — SQLAlchemy engine, session factory
- `app/core/security.py` — JWT utilities, Apple token validation
- `app/core/deps.py` — FastAPI auth dependencies

### Database Models
- `app/models/schema.py` — SQLAlchemy ORM models
- `app/models/user.py` — User model + auth schemas
- `app/models/metadata.py` — Content metadata models

### API Routers
- `app/routers/auth.py` — Apple Sign In, refresh tokens
- `app/routers/content.py` — Web UI routes
- `app/routers/admin.py` — Admin dashboard
- `app/routers/api/` — REST API endpoints

### Services Layer
- `app/services/openai_llm.py` — OpenAI integration
- `app/services/anthropic_llm.py` — Anthropic integration
- `app/services/google_flash.py` — Google Gemini integration
- `app/services/chat_agent.py` — pydantic-ai Deep Dive Chat

### Pipeline & Workers
- `app/pipeline/sequential_task_processor.py` — Main orchestrator
- `app/pipeline/worker.py` — Content processor
- `app/pipeline/podcast_workers.py` — Audio processing

### Scrapers
- `app/scraping/runner.py` — Scraper orchestrator
- `app/scraping/*_unified.py` — Per-source scrapers

### Processing Strategies
- `app/processing_strategies/registry.py` — Strategy registry
- `app/processing_strategies/*_strategy.py` — Content extractors

### iOS App
- `client/newsly/newsly/newslyApp.swift` — App entry
- `client/newsly/newsly/Services/APIClient.swift` — HTTP client
- `client/newsly/newsly/Services/AuthenticationService.swift` — Apple Sign In

---

## Appendix E: Dependencies

**Requires Python ≥3.13**. All dependencies managed via `uv` (defined in `pyproject.toml`).

### Core Web Framework
- `fastapi>=0.115.12` - Web framework
- `uvicorn>=0.34.2` - ASGI server
- `pydantic>=2.11.5` - Data validation
- `pydantic-settings>=2.9.1` - Configuration management
- `jinja2>=3.1.6` - HTML templates

### Database
- `sqlalchemy>=2.0.41` - ORM
- `alembic>=1.16.1` - Database migrations

### Authentication
- `pyjwt[crypto]` - JWT tokens
- `passlib[bcrypt]` - Password hashing
- `authlib>=1.6.5` - OAuth/Apple Sign In

### LLM Services
- `openai>=1.75.0` - OpenAI GPT
- `anthropic>=0.72.0` - Anthropic Claude
- `google-genai>=1.18.0` - Google Gemini
- `pydantic-ai>=0.1.0` - Agent framework
- `exa-py>=1.0.0` - Exa web search
- `tenacity>=9.1.2` - Retry logic

### Content Processing
- `crawl4ai>=0.7.4,<0.8` - HTML extraction
- `playwright>=1.53.0` - Browser automation
- `feedparser>=6.0.11` - RSS/Atom parsing
- `yt-dlp` - YouTube downloader
- `openai-whisper>=20250625` - Audio transcription

### Development & Testing
- `pytest>=8.3.5` - Testing framework
- `pytest-asyncio>=1.0.0` - Async test support
- `ruff>=0.11.12` - Linter/formatter

---

*Updated November 2025*
