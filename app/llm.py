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
from .schemas import ArticleSummary

# Removed global genai.configure(api_key=settings.GOOGLE_API_KEY)

def filter_article(content: str) -> tuple[bool, str]:
    """
    Decide whether an article matches user preferences using Google Gemini.
    Returns tuple of (matches: bool, reason: str).
    """
    system_prompt = """You are an intelligent news filter. Your task is to determine if an article matches the following preferences:

- Focus on technology, software development, AI, and business strategy.
- Prefer in-depth analysis over news reports.
- Include opinion pieces only if they provide detailed technical or strategic insights from recognized industry experts, even if they contain a minor promotional element.
- Exclude articles primarily intended as marketing or promotional material unless the promotional content is minimal and clearly secondary to substantial informative content.
    
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
        matches = result.get('matches', False)
        reason = result.get('reason', 'No reason provided')
        print(f"Filter result: matches={matches}, reason: {reason}")  # Log both result and reason
        return matches, reason
    except Exception as e:
        error_msg = f"Error during filtering: {str(e)}"
        print(f"Filter result: matches=False (error), reason: {error_msg}")
        return False, error_msg  # Default to excluding on error

def summarize_article(content: str) -> ArticleSummary:
    """
    Generate short and detailed summaries for the content using Google Gemini.
    Returns an ArticleSummary pydantic model.
    """
    system_prompt = """You are an expert at summarizing articles.
    
    You are going to create two summaries of the article.
    1. A Short 2 sentence summary for brief scanning.
    2. A detailed summary that starts with bullet points of the key topics
     and then a few paragraphs summarizing the document.

    Respond with a JSON object containing:
    {
        "short_summary": "2 sentence summary",
        "detailed_summary": "bullet points of the key topics, and multiple paragraph summary"
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
        
        # Parse JSON response and validate with Pydantic model
        summary_data = json.loads(response.text)
        return ArticleSummary(**summary_data)
    
    except Exception as e:
        print(f"Error in summarize_article: {e}")
        return ArticleSummary(
            short_summary="Error generating summary",
            detailed_summary="Error generating detailed summary"
        )

def summarize_pdf(pdf_data: bytes) -> ArticleSummary:
    """
    Generate short and detailed summaries for PDF content using Google Gemini.
    
    Args:
        pdf_data: Raw PDF bytes data
    
    Returns:
        ArticleSummary pydantic model
    """
    system_prompt = """You are an expert at summarizing PDF documents.
    
    You are going to create two summaries of the PDF document.
    1. A Short 2 sentence summary for brief scanning.
    2. A detailed summary that starts with bullet points of the key topics
     and then a few paragraphs summarizing the document.

    Respond with a JSON object containing:
    {
        "short_summary": "2 sentence summary",
        "detailed_summary": "bullet points of the key topics, and multiple paragraph summary"
    }"""

    try:
        # Initialize client with API key
        client = genai.Client(
            api_key=settings.GOOGLE_API_KEY,
        )

        model = "gemini-2.5-flash-preview-05-20"
        
        contents = [
            types.Part.from_bytes(
                data=pdf_data,
                mime_type='application/pdf',
            ),
            system_prompt
        ]
        generate_content_config = types.GenerateContentConfig(
            response_mime_type="application/json",
        )

        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=generate_content_config,
        )
        
        # Parse JSON response and validate with Pydantic model
        summary_data = json.loads(response.text)
        return ArticleSummary(**summary_data)
    
    except Exception as e:
        print(f"Error in summarize_pdf: {e}")
        return ArticleSummary(
            short_summary="Error generating PDF summary",
            detailed_summary="Error generating detailed PDF summary"
        )


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
