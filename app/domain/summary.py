from pydantic import BaseModel
from typing import Optional


class ArticleSummary(BaseModel):
    """Article summary model for LLM responses."""
    short_summary: str
    detailed_summary: str
    
    class Config:
        frozen = True