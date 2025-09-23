import json
from datetime import datetime
from pathlib import Path

from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.logging import get_logger
from app.core.settings import get_settings
from app.models.metadata import NewsSummary, StructuredSummary

logger = get_logger(__name__)
settings = get_settings()

# Create logs directory if it doesn't exist
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
ERRORS_DIR = LOG_DIR / "errors"
ERRORS_DIR.mkdir(exist_ok=True)
JSON_ERROR_LOG = ERRORS_DIR / "llm_json_errors.log"


def log_json_error(
    error_type: str, response_text: str, error: Exception, content_id: str | None = None
):
    """Log JSON parsing errors to a file for debugging."""
    timestamp = datetime.utcnow().isoformat()
    log_entry = {
        "timestamp": timestamp,
        "error_type": error_type,
        "content_id": content_id,
        "error_message": str(error),
        "response_text": response_text,
        "response_length": len(response_text)
        if response_text and isinstance(response_text, str)
        else 0,
    }

    try:
        with open(JSON_ERROR_LOG, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        logger.error(f"Failed to write to JSON error log: {e}")


def generate_summary_prompt(content_type: str, max_bullet_points: int, max_quotes: int, content: str) -> str:
    """Generate prompt based on content type"""
    if content_type == "hackernews":
        return f"""
        You are an expert content analyst. Analyze the following HackerNews discussion, which includes 
        the linked article content (if any) and community comments. Provide a structured summary that 
        captures both the main content and key insights from the discussion.
        
        Important:
        - Generate a descriptive title that captures the main theme (50-150 chars)
        - Start the title with "HN: " to indicate this is from HackerNews
        - The title should summoarize both the article topic AND the key discussion theme
        - Make it compelling - focus on the insight or controversy that sparked discussion
        - In the overview, include both article summary AND key discussion themes from comments
        - Extract actual quotes from both the article and notable comments
        - Make bullet points capture insights from BOTH content and discussion
        - Include {max_bullet_points} bullet points that blend article + comment insights
        - Include up to {max_quotes} notable quotes (can be from article or comments)
        - For quotes from comments, use format "HN user [username]" as context
        - Include 3-8 relevant topic tags
        - Add a "classification" field with either "to_read" or "skip"
        - Add a special section in the overview about the HN community response
        - Set "full_markdown" to include the article content AND a summary of key comments
        
        Classification Guidelines:
        - Consider both article quality AND discussion quality
        - High-quality technical discussions should be "to_read" even if article is average
        - Set to "skip" if both article and comments lack substance
        
        HackerNews Content and Discussion:
        {content}
        """
    elif content_type == "podcast":
        return f"""
        You are an expert content analyst. Analyze the following podcast transcript and provide a 
        structured summary with classification.
        
        Important:
        - Generate a descriptive title that captures the main theme (50-150 chars)
        - The title should be compelling and informative, summarizing the key point or insight
        - Include the blog/site name at the beginning in format "Site Name: Generated Title"
        - Extract the site name from the content (look for site headers, URL domain, bylines)
        - If no site name is found, use the domain name from the URL if available
        - The generated title should be different from the original article title - make it more descriptive
        - Focus on the "why it matters" aspect rather than just restating the topic
        - Extract actual quotes when available, don't paraphrase
        - Make bullet points specific and information dense
        - For the overview field: Start with a 50-100 word summary, then add 2-3 paragraphs (200-400 words) 
          that provide a comprehensive overview of the entire podcast conversation. This should allow 
          someone to quickly skim and understand the full context, main themes, and key takeaways.
        - Include {max_bullet_points} bullet points
        - Include up to {max_quotes} notable quotes if available - each quote should be 
          at least 2-3 sentences long to provide meaningful context and insight
        - Include 3-8 relevant topic tags
        - Add a "classification" field with either "to_read" or "skip"
        - Set "full_markdown" to an empty string "" (do not include the full transcript)
        
        Classification Guidelines:
        - Set classification to "skip" if the content:
          * Is light on content or seems like marketing/promotional material
          * Is general mainstream news without depth or unique insights
          * Lacks substantive information or analysis
          * Appears to be clickbait or sensationalized
        - Set classification to "to_read" if the content:
          * Contains in-depth analysis or unique insights
          * Provides technical or specialized knowledge
          * Offers original research or investigation
          * Has educational or informative value
        
        Podcast Transcript:
        {content}
        """
    elif content_type == "news_digest":
        return f"""
        You are an expert news editor. Read the article content (and any provided context) and produce
        a concise JSON object with the following fields:

        {{
          "title": "Descriptive headline (max 110 characters) highlighting the core takeaway",
          "article_url": "Canonical article URL",
          "key_points": [
            "Bullet #1 in 160 characters or less",
            "Bullet #2",
            "Bullet #3 (add up to {max_bullet_points} bullets total, prioritizing impact/implications)"
          ],
          "summary": "Optional 2-sentence overview (<= 280 characters). Omit or set to null if redundant.",
          "classification": "to_read" | "skip"
        }}

        Guidelines:
        - Focus on why the story matters rather than restating headlines.
        - Keep key points self-contained and specific. Do not start with repeated phrases.
        - Prefer action verbs and concrete figures/dates. Avoid fluff.
        - If context indicates low-quality or promotional content, set classification to "skip" and
          keep key points factual.
        - Never include markdown, topics, quotes, or code fences.
        - Return valid JSON only.

        Article & Context:
        {content}
        """
    else:
        # For articles and other content types, include full markdown
        return f"""
        You are an expert content analyst. Analyze the following content and provide a 
        structured summary with classification AND format the full text as clean markdown.
        
        Important:
        - Generate a descriptive title that captures the main theme (50-150 chars)
        - The title should be compelling and informative, summarizing the key point or insight
        - Extract the site name from the content (look for site headers, URL domain, bylines)
        - If no site name is found, use the domain name from the URL if available
        - The generated title should be different from the original article title - make it more descriptive
        - Focus on the "why it matters" aspect rather than just restating the topic
        - Extract actual quotes when available, don't paraphrase
        - Make bullet points specific and information dense
        - Ensure the overview provides context for someone who hasn't read the content
        - Overview should be 50-100 words, short and punchy
        - Include {max_bullet_points} bullet points
        - Include up to {max_quotes} notable quotes if available - each quote should be 
          at least 2-3 sentences long to provide meaningful context and insight
        - Include 3-8 relevant topic tags
        - Add a "classification" field with either "to_read" or "skip"
        - Add a "full_markdown" field with the entire content formatted as clean, readable markdown
        
        Classification Guidelines:
        - Set classification to "skip" if the content:
          * Is light on content or seems like marketing/promotional material
          * Is general mainstream news without depth or unique insights
          * Lacks substantive information or analysis
          * Appears to be clickbait or sensationalized
        - Set classification to "to_read" if the content:
          * Contains in-depth analysis or unique insights
          * Provides technical or specialized knowledge
          * Offers original research or investigation
          * Has educational or informative value
        
        Markdown Formatting Guidelines:
        - Format the full content as clean, readable markdown
        - Use proper heading hierarchy (# for main title, ## for sections, ### for subsections)
        - Preserve paragraphs with proper spacing
        - Format lists, quotes, and code blocks appropriately
        - Remove any unnecessary HTML artifacts or formatting issues
        - Make the content easy to read in markdown format
        
        Content:
        {content}
        """


def try_repair_truncated_json(json_str: str) -> str | None:
    """
    Attempt to repair truncated JSON by closing open structures.
    This is a best-effort approach for handling responses cut off by token limits.
    """
    try:
        # First, try to parse as-is
        json.loads(json_str)
        return json_str
    except json.JSONDecodeError:
        pass
    
    # Count open brackets/braces
    open_braces = json_str.count("{") - json_str.count("}")
    open_brackets = json_str.count("[") - json_str.count("]")
    
    # Try to repair by closing structures
    repaired = json_str
    
    # Close any open strings first
    if repaired.count('"') % 2 != 0:
        repaired += '"'
    
    # Close arrays and objects
    repaired += "]" * open_brackets
    repaired += "}" * open_braces
    
    try:
        json.loads(repaired)
        logger.info("Successfully repaired truncated JSON")
        return repaired
    except json.JSONDecodeError:
        # If simple repair didn't work, try more aggressive approach
        # Find the last complete element and truncate there
        for i in range(len(json_str) - 1, 0, -1):
            if json_str[i] in ['}', ']']:
                truncated = json_str[:i+1]
                # Balance the remaining structures
                open_braces = truncated.count("{") - truncated.count("}")
                open_brackets = truncated.count("[") - truncated.count("]")
                truncated += "]" * open_brackets
                truncated += "}" * open_braces
                
                try:
                    json.loads(truncated)
                    logger.info(f"Repaired JSON by truncating at position {i}")
                    return truncated
                except json.JSONDecodeError:
                    continue
        
        return None


class GoogleFlashService:
    """Google Flash (Gemini) service for content summarization."""

    def __init__(self):
        google_api_key = getattr(settings, "google_api_key", None)
        if not google_api_key:
            raise ValueError("Google API key is required for LLM service")

        from google import genai

        self.client = genai.Client(api_key=google_api_key)
        self.model_name = "gemini-2.5-flash-lite-preview-06-17"
        logger.info("Initialized Google Gemini provider for summarization")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def summarize_content(
        self, content: str, max_bullet_points: int = 6, max_quotes: int = 3, content_type: str = "article"
    ) -> StructuredSummary | NewsSummary | None:
        """Summarize content using LLM and classify it.

        Args:
            content: The content to summarize
            max_bullet_points: Maximum number of bullet points to generate (default: 6)
            max_quotes: Maximum number of quotes to extract (default: 3)
            content_type: Type of content - "article" or "podcast" (default: "article")

        Returns:
            StructuredSummary with bullet points, quotes, classification, and full_markdown
        """
        try:
            # Truncate content if too long
            if isinstance(content, bytes):
                content = content.decode("utf-8", errors="ignore")

            # Generate prompt based on content type
            prompt = generate_summary_prompt(content_type, max_bullet_points, max_quotes, content)

            # Define the schema for structured output
            # Use reasonable token limit for summaries
            if content_type == "podcast":
                max_tokens = 30000  # Smaller for podcasts since no full_markdown
                response_schema = StructuredSummary
            elif content_type == "news_digest":
                max_tokens = 8000
                response_schema = NewsSummary
            else:
                max_tokens = 50000  # Larger for articles to include full_markdown
                response_schema = StructuredSummary
            
            config = {
                "temperature": 0.7,
                "max_output_tokens": max_tokens,
                "response_mime_type": "application/json",
                "response_schema": response_schema,
            }

            response = self.client.models.generate_content(
                model=self.model_name, contents=prompt, config=config
            )

            # Handle response structure properly
            response_text = None
            
            # Check if response was truncated due to MAX_TOKENS
            if hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, "finish_reason") and str(candidate.finish_reason) == "FinishReason.MAX_TOKENS":
                    logger.warning("Response was truncated due to MAX_TOKENS limit")
                    # Try to extract partial response
                    if hasattr(candidate, "content") and hasattr(candidate.content, "parts") and candidate.content.parts:
                        parts_text = []
                        for part in candidate.content.parts:
                            if hasattr(part, "text"):
                                parts_text.append(part.text)
                        response_text = "".join(parts_text)
                        if response_text:
                            logger.info(f"Extracted partial response of length {len(response_text)}")
                        else:
                            logger.error("No text found in truncated response")
                            log_json_error(
                                "no_response_text", 
                                str(response)[:1000],
                                Exception("No text in truncated response"),
                                content_id=str(id(content))
                            )
                            return None
            
            # Normal response extraction
            if not response_text:
                if hasattr(response, "text"):
                    response_text = response.text
                elif hasattr(response, "parts"):
                    parts_text = []
                    for part in response.parts:
                        if hasattr(part, "text"):
                            parts_text.append(part.text)
                    response_text = "".join(parts_text)
                elif hasattr(response, "candidates") and response.candidates:
                    candidate = response.candidates[0]
                    if hasattr(candidate, "content") and hasattr(candidate.content, "parts"):
                        parts_text = []
                        for part in candidate.content.parts:
                            if hasattr(part, "text"):
                                parts_text.append(part.text)
                        response_text = "".join(parts_text)

            if not response_text:
                logger.error(f"No text found in response: {response}")
                log_json_error(
                    "no_response_text", 
                    str(response)[:1000],
                    Exception("No text in response"),
                    content_id=str(id(content))
                )
                return None

            # Clean response if wrapped in markdown code blocks
            cleaned_text = response_text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            elif cleaned_text.startswith("```"):
                cleaned_text = cleaned_text[3:]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]
            cleaned_text = cleaned_text.strip()
            
            # Additional cleanup for common issues
            if not cleaned_text:
                logger.error("Cleaned text is empty after removing markdown blocks")
                log_json_error(
                    "empty_cleaned_text",
                    response_text,
                    Exception("Empty text after cleanup"),
                    content_id=str(id(content))
                )
                return None
            
            # Check for common error responses
            if cleaned_text.lower() in ["this is not valid json", "invalid json", "error"]:
                logger.error(f"LLM returned error response: {cleaned_text}")
                log_json_error(
                    "llm_error_response",
                    response_text,
                    Exception(f"LLM error: {cleaned_text}"),
                    content_id=str(id(content))
                )
                return None

            # Parse the structured response
            try:
                summary_data = json.loads(cleaned_text)
            except json.JSONDecodeError as e:
                logger.warning(f"Initial JSON parse failed: {e}")
                # Try to repair truncated JSON
                repaired_text = try_repair_truncated_json(cleaned_text)
                if repaired_text:
                    try:
                        summary_data = json.loads(repaired_text)
                        logger.info("Successfully parsed repaired JSON")
                    except json.JSONDecodeError:
                        raise e  # Re-raise original error
                else:
                    raise e  # Re-raise original error

            # Instantiate the appropriate summary model
            model_cls = response_schema
            summary_obj = model_cls(**summary_data)
            return summary_obj

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in structured summary: {e}")
            logger.error(
                f"Response was: "
                f"{response_text[:500] if 'response_text' in locals() else 'No response'}"
            )
            log_json_error(
                "json_decode_error",
                response_text if "response_text" in locals() else "No response text",
                e,
                content_id=str(id(content)),
            )
            return None
        except Exception as e:
            logger.error(f"Error generating structured summary: {e}")
            log_json_error(
                "unexpected_error",
                response_text if "response_text" in locals() else "No response text",
                e,
                content_id=str(id(content)),
            )
            return None


# Global instance
_google_flash_service = None


def get_google_flash_service() -> GoogleFlashService:
    """Get the global Google Flash service instance."""
    global _google_flash_service
    if _google_flash_service is None:
        _google_flash_service = GoogleFlashService()
    return _google_flash_service
