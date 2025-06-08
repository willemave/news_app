"""
This module manages the LLM integration for:
1. Preference-based filtering.
2. Summarization (short and detailed).

Uses Google Gemini Flash 2.5 for all LLM operations.
"""
import json
from google import genai
from google.genai import types
from .config import settings
from .schemas import ArticleSummary

# Removed global genai.configure(api_key=settings.GOOGLE_API_KEY)

def _unescape_json_string(escaped_string: str) -> str:
    """
    Properly unescape a JSON string, handling all standard JSON escape sequences.
    """
    # Handle standard JSON escape sequences
    unescaped = escaped_string.replace('\\"', '"')
    unescaped = unescaped.replace('\\\\', '\\')
    unescaped = unescaped.replace('\\/', '/')
    unescaped = unescaped.replace('\\b', '\b')
    unescaped = unescaped.replace('\\f', '\f')
    unescaped = unescaped.replace('\\n', '\n')
    unescaped = unescaped.replace('\\r', '\r')
    unescaped = unescaped.replace('\\t', '\t')
    
    # Handle unicode escape sequences (\uXXXX)
    import re
    def replace_unicode(match):
        return chr(int(match.group(1), 16))
    
    unescaped = re.sub(r'\\u([0-9a-fA-F]{4})', replace_unicode, unescaped)
    
    return unescaped

def _normalize_summary_data(summary_data: dict) -> dict:
    """
    Normalize summary data to ensure all fields are strings.
    Converts lists to formatted strings if needed.
    """
    normalized = summary_data.copy()
    
    # Handle short_summary
    if isinstance(normalized.get('short_summary'), list):
        normalized['short_summary'] = ' '.join(str(item) for item in normalized['short_summary'])
    
    # Handle detailed_summary
    if isinstance(normalized.get('detailed_summary'), list):
        # Format list items as bullet points
        items = [str(item) for item in normalized['detailed_summary']]
        normalized['detailed_summary'] = '\n'.join(f"• {item}" for item in items)
    
    return normalized

def _parse_malformed_summary_response(response_text: str) -> ArticleSummary:
    """
    Fallback parser for malformed JSON responses from LLM.
    Attempts to extract short_summary and detailed_summary from the response.
    """
    import re
    
    try:
        # Try to find short_summary and detailed_summary in the response
        # More robust regex patterns that handle various malformed JSON scenarios
        # Pattern 1: Try to match complete quoted strings with proper delimiters
        short_match = re.search(r'"short_summary"\s*:\s*"((?:[^"\\]|\\.)*)"\s*[,}\n]', response_text, re.DOTALL)
        detailed_match = re.search(r'"detailed_summary"\s*:\s*"((?:[^"\\]|\\.)*)"\s*[,}\n]', response_text, re.DOTALL)
        
        # Pattern 2: If that fails, try to match even without proper closing delimiters (for truncated responses)
        if not short_match:
            short_match = re.search(r'"short_summary"\s*:\s*"((?:[^"\\]|\\.)*)', response_text, re.DOTALL)
        
        if not detailed_match:
            detailed_match = re.search(r'"detailed_summary"\s*:\s*"((?:[^"\\]|\\.)*)', response_text, re.DOTALL)
        
        short_summary = "Error parsing summary"
        detailed_summary = "Error parsing detailed summary"
        
        if short_match:
            short_summary = _unescape_json_string(short_match.group(1))
        
        if detailed_match:
            detailed_summary = _unescape_json_string(detailed_match.group(1))
        
        return ArticleSummary(
            short_summary=short_summary,
            detailed_summary=detailed_summary
        )
    except Exception as e:
        print(f"Error in fallback parsing: {e}")
        return ArticleSummary(
            short_summary="Error parsing summary",
            detailed_summary="Error parsing detailed summary"
        )

def _parse_malformed_filter_response(response_text: str) -> tuple[bool, str]:
    """
    Fallback parser for malformed JSON responses from filter_article.
    Attempts to extract matches and reason from the response.
    """
    import re
    
    try:
        # Try to find matches and reason in the response
        matches_match = re.search(r'"matches"\s*:\s*(true|false)', response_text, re.IGNORECASE)
        reason_match = re.search(r'"reason"\s*:\s*"((?:[^"\\]|\\.)*)"\s*[,}]', response_text, re.DOTALL)
        
        matches = False
        reason = "Error parsing filter response"
        
        if matches_match:
            matches = matches_match.group(1).lower() == 'true'
        
        if reason_match:
            reason = _unescape_json_string(reason_match.group(1))
        
        print(f"Filter result (fallback): matches={matches}, reason: {reason}")
        return matches, reason
    except Exception as e:
        print(f"Error in fallback filter parsing: {e}")
        return False, "Error parsing filter response"

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
        
        # Parse JSON response with error handling
        try:
            result = json.loads(response.text)
            matches = result.get('matches', False)
            reason = result.get('reason', 'No reason provided')
            print(f"Filter result: matches={matches}, reason: {reason}")
            return matches, reason
        except json.JSONDecodeError as json_error:
            print(f"JSON parsing error in filter_article: {json_error}")
            print(f"Raw response text: {response.text[:500]}...")
            # Try fallback parsing for filter response
            return _parse_malformed_filter_response(response.text)
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

    IMPORTANT: Both fields must be strings, not arrays. Format bullet points as text with line breaks.

    Respond with a JSON object containing:
    {
        "short_summary": "2 sentence summary as a string",
        "detailed_summary": "• Key topic 1\n• Key topic 2\n• Key topic 3\n\nDetailed paragraph summary..."
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
        try:
            summary_data = json.loads(response.text)
            # Normalize data to handle lists
            normalized_data = _normalize_summary_data(summary_data)
            return ArticleSummary(**normalized_data)
        except json.JSONDecodeError as json_error:
            print(f"JSON parsing error in summarize_article: {json_error}")
            print(f"Raw response text: {response.text[:500]}...")  # Log first 500 chars for debugging
            # Try to extract summaries from malformed JSON using fallback parsing
            return _parse_malformed_summary_response(response.text)
    
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

    IMPORTANT: Both fields must be strings, not arrays. Format bullet points as text with line breaks.

    Respond with a JSON object containing:
    {
        "short_summary": "2 sentence summary as a string",
        "detailed_summary": "• Key topic 1\n• Key topic 2\n• Key topic 3\n\nDetailed paragraph summary..."
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
        try:
            summary_data = json.loads(response.text)
            # Normalize data to handle lists
            normalized_data = _normalize_summary_data(summary_data)
            return ArticleSummary(**normalized_data)
        except json.JSONDecodeError as json_error:
            print(f"JSON parsing error in summarize_pdf: {json_error}")
            print(f"Raw response text: {response.text[:500]}...")
            # Try to extract summaries from malformed JSON using fallback parsing
            return _parse_malformed_summary_response(response.text)
    
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

def summarize_podcast_transcript(transcript_text: str) -> ArticleSummary:
    """
    Generate short and detailed summaries for podcast transcript content using Google Gemini.
    
    Args:
        transcript_text: The transcript text from the podcast
    
    Returns:
        ArticleSummary pydantic model
    """
    system_prompt = """You are an expert at summarizing podcast transcripts.
    
    You are going to create two summaries of the podcast transcript.
    1. A Short 2 sentence summary for brief scanning.
    2. A detailed summary that starts with bullet points of the key topics discussed
     and then a few paragraphs summarizing the main points and insights from the podcast.

    IMPORTANT: Both fields must be strings, not arrays. Format bullet points as text with line breaks.

    Respond with a JSON object containing:
    {
        "short_summary": "2 sentence summary as a string",
        "detailed_summary": "• Key topic 1\n• Key topic 2\n• Key topic 3\n\nDetailed paragraph summary..."
    }"""

    try:
        # Initialize client with API key
        client = genai.Client(
            api_key=settings.GOOGLE_API_KEY,
        )

        model = "gemini-2.5-flash-preview-05-20"
        prompt = f"{system_prompt}\n\nPodcast transcript:\n{transcript_text}"
        
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
        try:
            summary_data = json.loads(response.text)
            # Normalize data to handle lists
            normalized_data = _normalize_summary_data(summary_data)
            return ArticleSummary(**normalized_data)
        except json.JSONDecodeError as json_error:
            print(f"JSON parsing error in summarize_podcast_transcript: {json_error}")
            print(f"Raw response text: {response.text[:500]}...")
            # Try to extract summaries from malformed JSON using fallback parsing
            return _parse_malformed_summary_response(response.text)
    
    except Exception as e:
        print(f"Error in summarize_podcast_transcript: {e}")
        return ArticleSummary(
            short_summary="Error generating podcast summary",
            detailed_summary="Error generating detailed podcast summary"
        )
