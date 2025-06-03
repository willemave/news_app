import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

# Basic Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler() # Log to console
    ]
)

# Get a logger instance
logger = logging.getLogger(__name__)

class Settings:
    def __init__(self, **kwargs):
        self.RAINDROP_TOKEN: str = kwargs.get("RAINDROP_TOKEN", os.getenv("RAINDROP_TOKEN", ""))
        self.LLM_API_KEY: str = kwargs.get("LLM_API_KEY", os.getenv("LLM_API_KEY", ""))
        self.GOOGLE_API_KEY: str = kwargs.get("GOOGLE_API_KEY", os.getenv("GOOGLE_API_KEY", ""))
        self.DATABASE_URL: str = kwargs.get("DATABASE_URL", os.getenv("DATABASE_URL", "sqlite:///./news_app.db"))
        self.REDDIT_CLIENT_ID: str = kwargs.get("REDDIT_CLIENT_ID", os.getenv("REDDIT_CLIENT_ID", ""))
        self.REDDIT_CLIENT_SECRET: str = kwargs.get("REDDIT_CLIENT_SECRET", os.getenv("REDDIT_CLIENT_SECRET", ""))
        self.REDDIT_USER_AGENT: str = kwargs.get("REDDIT_USER_AGENT", os.getenv("REDDIT_USER_AGENT", "news_app"))
        self.HUEY_DB_PATH: str = kwargs.get("HUEY_DB_PATH", os.getenv("HUEY_DB_PATH", "./db/huey.db"))

        # Settings for RobustHttpClient
        self.HTTP_CLIENT_TIMEOUT: float = float(kwargs.get("HTTP_CLIENT_TIMEOUT", os.getenv("HTTP_CLIENT_TIMEOUT", "15.0")))
        self.HTTP_CLIENT_USER_AGENT: str = kwargs.get("HTTP_CLIENT_USER_AGENT", os.getenv("HTTP_CLIENT_USER_AGENT", "NewsApp/1.0 (GlobalDefaultClient)"))

# Per-subreddit fetch limits
SUBREDDIT_LIMITS = {
    "front": 30,
    "technology": 80,
    "ai": 120,
    "*": 50        # default
}

settings = Settings()
