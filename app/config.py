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
    RAINDROP_TOKEN: str = os.getenv("RAINDROP_TOKEN", "")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./news_app.db")
    REDDIT_CLIENT_ID: str = os.getenv("REDDIT_CLIENT_ID", "")
    REDDIT_CLIENT_SECRET: str = os.getenv("REDDIT_CLIENT_SECRET", "")
    REDDIT_USER_AGENT: str = os.getenv("REDDIT_USER_AGENT", "news_app")

settings = Settings()
