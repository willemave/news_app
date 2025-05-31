"""
This module manages the LLM integration for:
1. Preference-based filtering.
2. Summarization (short and detailed).

Uses Google Gemini Flash 2.5 for all LLM operations.
"""
import json
import os
from google import genai
from google.genai import types
from .config import settings

# Removed global genai.configure(api_key=settings.GOOGLE_API_KEY)

def filter_article(content: str) -> bool:
    """
    Decide whether an article matches user preferences using Google Gemini.
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
        # Initialize client with API key
        client = genai.Client(
            api_key=settings.GOOGLE_API_KEY,
        )

        model = "gemini-2.5-flash-preview-05-20"
        prompt = f"{system_prompt}\n\nArticle content:\n{content}"
        
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=prompt),
                ],
            ),
        ]
        generate_content_config = types.GenerateContentConfig(
            response_mime_type="application/json",
        )

        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=generate_content_config,
        )
        
        # It's good practice to check if response.text is valid JSON before loading
        # For now, assuming it's valid as per original code
        result = json.loads(response.text)
        print(f"Filter reason: {result.get('reason')}")  # Logging for debugging
        return result.get('matches', False)
    except Exception as e:
        print(f"Error in filter_article: {e}")
        return False  # Default to excluding on error

def summarize_article(content: str) -> dict[str, str]:
    """
    Generate short and detailed summaries for the content using Google Gemini.
    Returns a tuple of (short_summary, detailed_summary).
    """
    system_prompt = """You are an expert at summarizing articles. 
    
    You are going to create two summaries of the article. 
    1. A Short 2 sentence summary for brief scanning. 
    2. A detailed summary that starts with bullet points of the key topics
     and then a few paragraphs summarizing the document.
    3. Please pull out a set of relevant keywords. 

    Respond with a JSON object containing:
    {
        "short": "2 sentence summary",
        "detailed": "bullet points of the key topics, and multiple paragraph summary" 
        "keywords": ["list", "of", "relevant", "keywords"]
    }"""

    try:
        # Initialize client with API key
        client = genai.Client(
            api_key=settings.GOOGLE_API_KEY,
        )

        model = "gemini-2.5-flash-preview-05-20"
        prompt = f"{system_prompt}\n\nArticle content:\n{content}"
        
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=prompt),
                ],
            ),
        ]
        generate_content_config = types.GenerateContentConfig(
            response_mime_type="application/json",
        )

        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=generate_content_config,
        )
        
        return json.loads(response.text)
    
    except Exception as e:
        print(f"Error in summarize_article: {e}")
        return ("Error generating summary", "Error generating detailed summary")

def summarize_text(content: str) -> str:
    """
    Generate a summary for the given text content using Google Gemini.
    This is a simplified function for basic summarization needs.
    Returns a single summary string.
    """
    prompt = f"""Please provide a concise summary of the following article content in 2-3 sentences:

{content}"""

    try:
        # Initialize client with API key
        client = genai.Client(
            api_key=settings.GOOGLE_API_KEY,
        )

        model = "gemini-2.5-flash-preview-05-20"
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=prompt),
                ],
            ),
        ]
        generate_content_config = types.GenerateContentConfig(
            response_mime_type="text/plain",
        )

        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=generate_content_config,
        )
        return response.text.strip()
    except Exception as e:
        print(f"Error in summarize_text: {e}")
        return "Error generating summary"
