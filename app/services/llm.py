import json
from datetime import datetime
from pathlib import Path

from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.logging import get_logger
from app.core.settings import get_settings
from app.models.metadata import ContentQuote, StructuredSummary, SummaryBulletPoint

logger = get_logger(__name__)
settings = get_settings()

# Create logs directory if it doesn't exist
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
JSON_ERROR_LOG = LOG_DIR / "llm_json_errors.log"


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
        "response_length": len(response_text) if response_text and isinstance(response_text, str) else 0,
    }

    try:
        with open(JSON_ERROR_LOG, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        logger.error(f"Failed to write to JSON error log: {e}")


class LLMService:
    """LLM service using Google Gemini for content summarization."""

    def __init__(self):
        google_api_key = getattr(settings, "google_api_key", None)
        if not google_api_key:
            raise ValueError("Google API key is required for LLM service")
            
        from google import genai
        self.client = genai.Client(api_key=google_api_key)
        self.model_name = "gemini-2.5-flash-lite-preview-06-17"
        logger.info("Initialized Google Gemini provider for summarization")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def summarize_content(
        self, content: str, max_bullet_points: int = 6, max_quotes: int = 3
    ) -> StructuredSummary | None:
        """Summarize content using LLM and classify it.

        Args:
            content: The content to summarize
            max_bullet_points: Maximum number of bullet points to generate (default: 6)
            max_quotes: Maximum number of quotes to extract (default: 3)

        Returns:
            StructuredSummary with bullet points, quotes, classification, and full_markdown
        """
        try:
            # Truncate content if too long
            if isinstance(content, bytes):
                content = content.decode("utf-8", errors="ignore")

            # Truncate content if too long to fit in context window
            if len(content) > 15000:
                content = content[:15000] + "..."

            prompt = f"""
            You are an expert content analyst. Analyze the following content and provide a 
            structured summary with classification AND format the full text as clean markdown.
            
            Important:
            - Generate a descriptive title that captures the main theme (10-200 chars)
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

            # Define the schema for structured output
            config = {
                "temperature": 0.7,
                "max_output_tokens": 50000,  # Increased to prevent truncation
                "response_mime_type": "application/json",
                "response_schema": StructuredSummary,
            }

            response = self.client.models.generate_content(
                model=self.model_name, contents=prompt, config=config
            )

            # Handle response structure properly
            response_text = None
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
                return None

            # Clean response if wrapped in markdown code blocks
            cleaned_text = response_text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]
            cleaned_text = cleaned_text.strip()
            
            # Parse the structured response
            summary_data = json.loads(cleaned_text)
            
            # Create and return StructuredSummary
            return StructuredSummary(**summary_data)

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

    def summarize_content_sync(
        self, content: str, max_bullet_points: int = 6, max_quotes: int = 3
    ) -> StructuredSummary | None:
        """Synchronous version of summarize_content.

        Args:
            content: The content to summarize
            max_bullet_points: Maximum number of bullet points to generate (default: 6)
            max_quotes: Maximum number of quotes to extract (default: 3)

        Returns:
            StructuredSummary with bullet points, quotes, classification, and full_markdown
        """
        try:
            # Truncate content if too long
            if isinstance(content, bytes):
                content = content.decode("utf-8", errors="ignore")

            # Truncate content if too long to fit in context window
            if len(content) > 15000:
                content = content[:15000] + "..."

            prompt = f"""
            You are an expert content analyst. Analyze the following content and provide a 
            structured summary with classification AND format the full text as clean markdown.
            
            Important:
            - Generate a descriptive title that captures the main theme (10-200 chars)
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

            # Define the schema for structured output
            config = {
                "temperature": 0.7,
                "max_output_tokens": 50000,  # Increased to prevent truncation
                "response_mime_type": "application/json",
                "response_schema": StructuredSummary,
            }

            response = self.client.models.generate_content(
                model=self.model_name, contents=prompt, config=config
            )

            # Handle response structure properly
            response_text = None
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
                return None

            # Clean response if wrapped in markdown code blocks
            cleaned_text = response_text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]
            cleaned_text = cleaned_text.strip()
            
            # Parse the structured response
            summary_data = json.loads(cleaned_text)
            
            # Create and return StructuredSummary
            return StructuredSummary(**summary_data)

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in sync structured summary: {e}")
            return None
        except Exception as e:
            logger.error(f"Error generating sync structured summary: {e}")
            return None


# Global instance
_llm_service = None


def get_llm_service() -> LLMService:
    """Get the global LLM service instance."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service