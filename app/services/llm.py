import json
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

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
        "response_length": len(response_text) if response_text else 0,
    }

    try:
        with open(JSON_ERROR_LOG, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        logger.error(f"Failed to write to JSON error log: {e}")


class LLMProvider(ABC):
    """Abstract base for LLM providers."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
    ) -> str:
        """Generate text from prompt."""
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI API provider."""

    def __init__(self, api_key: str):
        import openai

        self.client = openai.AsyncOpenAI(api_key=api_key)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def generate(
        self, prompt: str, system_prompt: str | None = None, temperature: float = 0.7
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=temperature,
        )

        return response.choices[0].message.content


class GoogleProvider(LLMProvider):
    """Google Generative AI provider using Gemini Flash 2.5."""

    def __init__(self, api_key: str):
        from google import genai

        self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-2.5-flash-preview-05-20"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
    ) -> str:
        # Combine system prompt and user prompt
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        config = {
            "temperature": temperature,
            "max_output_tokens": 50000,  # Increased to prevent truncation
        }

        try:
            # Use synchronous method in async context
            response = self.client.models.generate_content(
                model=self.model_name, contents=full_prompt, config=config
            )

            # Handle response structure properly
            if hasattr(response, "text"):
                return response.text
            elif hasattr(response, "parts"):
                # Handle multi-part responses
                parts_text = []
                for part in response.parts:
                    if hasattr(part, "text"):
                        parts_text.append(part.text)
                return "".join(parts_text)
            elif hasattr(response, "candidates") and response.candidates:
                # Handle candidate responses
                candidate = response.candidates[0]
                if hasattr(candidate, "content") and hasattr(candidate.content, "parts"):
                    parts_text = []
                    for part in candidate.content.parts:
                        if hasattr(part, "text"):
                            parts_text.append(part.text)
                    return "".join(parts_text)

            # Fallback: try to convert to string
            return str(response)
        except Exception as e:
            logger.error(f"Error in Google generate: {e}")
            raise


class MockProvider(LLMProvider):
    """Mock provider for testing."""

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
    ) -> str:
        # Return a mock structured summary response
        mock_response = {
            "title": "Mock Content Analysis Reveals Key Testing Insights",
            "overview": (
                "This is a comprehensive mock overview that provides detailed context "
                "about the content being summarized. It meets the minimum length "
                "requirement for validation and gives readers a clear understanding "
                "of the main themes."
            ),
            "bullet_points": [
                {"text": "First key finding from the mock analysis", "category": "key_finding"},
                {"text": "Important methodology used in the process", "category": "methodology"},
                {"text": "Significant conclusion drawn from the data", "category": "conclusion"},
            ],
            "quotes": [
                {"text": "This is a notable quote from the content", "context": "Mock Author"}
            ],
            "topics": ["Testing", "Mock Data", "Summary"],
        }
        return json.dumps(mock_response)


class LLMService:
    """Unified LLM service with provider abstraction."""

    def __init__(self):
        self.provider = self._initialize_provider()

    def _initialize_provider(self) -> LLMProvider:
        """Initialize the appropriate LLM provider."""
        # Check for Google API key first (for summarization)
        google_api_key = getattr(settings, "google_api_key", None)
        if google_api_key:
            logger.info("Using Google provider for summarization")
            return GoogleProvider(google_api_key)
        elif settings.openai_api_key:
            logger.info("Using OpenAI provider")
            return OpenAIProvider(settings.openai_api_key)
        else:
            logger.warning("No LLM API key configured, using mock provider")
            return MockProvider()

    async def summarize_content(
        self, content: str, max_bullet_points: int = 6, max_quotes: int = 3
    ) -> StructuredSummary | dict[str, Any] | None:
        """Summarize content using LLM.

        Args:
            content: The content to summarize
            max_bullet_points: Maximum number of bullet points to generate (default: 6)
            max_quotes: Maximum number of quotes to extract (default: 3)

        Returns:
            StructuredSummary with bullet points and quotes, None if error
        """
        try:
            # Truncate content if too long
            if isinstance(content, bytes):
                content = content.decode("utf-8", errors="ignore")

            # Truncate content if too long to fit in context window
            if len(content) > 15000:
                content = content[:15000] + "..."

            # Use structured output for GoogleProvider
            if isinstance(self.provider, GoogleProvider):
                prompt = f"""
                You are an expert content analyst. Analyze the following content and provide a 
                structured summary.
                
                Important:
                - Generate a descriptive title that captures the main theme (10-200 chars)
                - Extract actual quotes when available, don't paraphrase
                - Make bullet points specific and information dense
                - Ensure the overview provides context for someone who hasn't read the content
                - Overview should be 50-100 words, short and punchy
                - Include {max_bullet_points} bullet points
                - Include up to {max_quotes} notable quotes if available
                - Include 3-8 relevant topic tags
                
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

                try:
                    response = self.provider.client.models.generate_content(
                        model=self.provider.model_name, contents=prompt, config=config
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
                        log_json_error(
                            "no_response_text", str(response), Exception("No text in response")
                        )
                        # Check if response was truncated due to max tokens
                        if hasattr(response, "candidates") and response.candidates:
                            candidate = response.candidates[0]
                            if (
                                hasattr(candidate, "finish_reason")
                                and str(candidate.finish_reason) == "FinishReason.MAX_TOKENS"
                            ):
                                logger.error("Response truncated due to max tokens limit")
                        return None

                    # Parse the structured response
                    summary_data = json.loads(response_text)
                except (AttributeError, TypeError) as e:
                    logger.error(f"Error accessing response text: {e}")
                    log_json_error(
                        "response_access_error",
                        str(response) if "response" in locals() else "No response",
                        e,
                    )
                    return None
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error in Google response: {e}")
                    log_json_error(
                        "google_json_decode_error",
                        response_text if "response_text" in locals() else "No response text",
                        e,
                    )
                    # Try to extract partial JSON if possible
                    if "response_text" in locals() and response_text:
                        # Check if the response was truncated
                        if response_text.count('"') % 2 != 0:
                            logger.error("Response appears to be truncated (unmatched quotes)")
                        # Try to fix common truncation issues
                        try:
                            # Add closing brackets/braces if missing
                            fixed_json = response_text
                            open_braces = fixed_json.count("{") - fixed_json.count("}")
                            open_brackets = fixed_json.count("[") - fixed_json.count("]")

                            # Close any open strings first
                            if fixed_json.count('"') % 2 != 0:
                                fixed_json += '"'

                            # Close open arrays and objects
                            fixed_json += "]" * open_brackets + "}" * open_braces

                            summary_data = json.loads(fixed_json)
                            logger.warning("Successfully parsed truncated JSON after fixing")
                        except Exception:
                            logger.error("Could not fix truncated JSON")
                            return None
                    else:
                        return None
            else:
                # For other providers, use the prompt-based approach
                prompt = f"""
                Analyze the following content and provide a structured summary in JSON format 
                with these exact fields:
                
                1. "title": A descriptive, engaging title that captures the main theme 
                   (10-200 chars)
                2. "overview": A brief overview paragraph (50-200 words) that captures the 
                   main theme and significance
                3. "bullet_points": An array of {max_bullet_points} key points, each as an object 
                   with:
                   - "text": The bullet point text (concise, informative, 10-100 words)
                   - "category": One of: "key_finding", "methodology", "conclusion", 
                     "insight", "announcement", "warning", "recommendation"
                4. "quotes": Up to {max_quotes} notable quotes from the content, each as an 
                   object with:
                   - "text": The exact quote (if available)
                   - "context": Who said it or where it comes from
                5. "topics": An array of 3-8 relevant topic tags 
                   (e.g., "AI", "Technology", "Business")
                
                Important:
                - Generate a descriptive title that would make someone want to read the content
                - Extract actual quotes when available, don't paraphrase
                - Make bullet points specific and information dense
                - Ensure the overview provides context for someone who hasn't read the content
                - Return ONLY valid JSON, no additional text
                
                Content:
                {content}
                
                JSON Summary:
                """

                response = await self.provider.generate(
                    prompt=prompt,
                    system_prompt=(
                        "You are an expert content analyst. Always return valid JSON "
                        "that matches the exact schema requested. Be concise but informative."
                    ),
                    temperature=0.5,
                )

                # Clean the response to ensure it's valid JSON
                response_text = response.strip()
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
                response_text = response_text.strip()

                # Parse JSON response
                summary_data = json.loads(response_text)

            # Validate and create structured summary
            structured_summary = StructuredSummary(
                title=summary_data.get("title", "Untitled Content"),
                overview=summary_data.get("overview", ""),
                bullet_points=[
                    SummaryBulletPoint(text=bp.get("text", ""), category=bp.get("category"))
                    for bp in summary_data.get("bullet_points", [])
                ],
                quotes=[
                    ContentQuote(text=q.get("text", ""), context=q.get("context"))
                    for q in summary_data.get("quotes", [])
                ],
                topics=summary_data.get("topics", []),
                summarization_date=datetime.utcnow(),
            )

            return structured_summary

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in structured summary: {e}")
            logger.error(
                f"Response was: "
                f"{response_text[:500] if 'response_text' in locals() else 'No response'}"
            )
            # Log the full response for debugging
            log_json_error(
                "json_decode_error",
                response_text if "response_text" in locals() else "No response text",
                e,
                content_id=str(id(content)),  # Use object id as temporary identifier
            )
            # Return as dict for backward compatibility
            return {
                "overview": "Failed to generate summary due to JSON parsing error",
                "bullet_points": [],
                "quotes": [],
                "topics": [],
                "summarization_date": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"Error generating structured summary: {e}")
            # Log any unexpected errors
            log_json_error(
                "unexpected_error",
                response_text if "response_text" in locals() else "No response text",
                e,
                content_id=str(id(content)),
            )
            return None


# Global instance
_llm_service = None


def get_llm_service() -> LLMService:
    """Get the global LLM service instance."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
