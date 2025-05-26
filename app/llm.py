"""
This module manages the LLM integration for:
1. Preference-based filtering.
2. Summarization (short and detailed).

You can use OpenAI or any other provider with the appropriate client library.
"""
import os
import json
from openai import OpenAI
from .config import settings

# Initialize OpenAI client
client = OpenAI(api_key=settings.LLM_API_KEY)

def filter_article(content: str) -> bool:
    """
    Decide whether an article matches user preferences using OpenAI.
    Returns True if the article matches preferences, False otherwise.
    """
    system_prompt = """You are an intelligent news filter. Your task is to determine if an article matches the following preferences:
    - Focus on technology, software development, AI, and business strategy
    - Prefer in-depth analysis over news reports
    - Exclude opinion pieces unless they're from recognized industry experts
    - Exclude articles that are primarily marketing or promotional
    
    Respond with a JSON object containing:
    {
        "matches": boolean,
        "reason": "brief explanation of decision"
    }"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content}
            ],
            temperature=0.3,
            max_tokens=150,
            response_format={ "type": "json_object" }
        )
        
        result = json.loads(response.choices[0].message.content)
        print(f"Filter reason: {result.get('reason')}")  # Logging for debugging
        return result.get('matches', False)
    except Exception as e:
        print(f"Error in filter_article: {e}")
        return False  # Default to excluding on error

def summarize_article(content: str) -> tuple[str, str]:
    """
    Generate short and detailed summaries for the content using OpenAI.
    Returns a tuple of (short_summary, detailed_summary).
    """
    system_prompt = """You are an expert at summarizing articles. Create two summaries:
    1. A short summary (2-3 sentences) that captures the main point
    2. A detailed summary that includes key points, important details, and any relevant data or quotes

    Respond with a JSON object containing:
    {
        "short_summary": "2-3 sentence summary",
        "detailed_summary": "comprehensive summary with key points",
        "keywords": ["list", "of", "relevant", "keywords"]
    }"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",  # Using GPT-4 for better summarization
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content}
            ],
            temperature=0.7,
            max_tokens=1000,
            response_format={ "type": "json_object" }
        )
        
        result = json.loads(response.choices[0].message.content)
        
        # Log keywords for potential future use
        print(f"Keywords: {', '.join(result.get('keywords', []))}")
        
        return (
            result.get('short_summary', "Error generating summary"),
            result.get('detailed_summary', "Error generating detailed summary")
        )
    except Exception as e:
        print(f"Error in summarize_article: {e}")
        return ("Error generating summary", "Error generating detailed summary")
