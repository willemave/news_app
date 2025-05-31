import os
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

class Settings:
    RAINDROP_TOKEN: str = os.getenv("RAINDROP_TOKEN", "")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./news_app.db")

settings = Settings()
