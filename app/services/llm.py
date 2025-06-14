from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod
import json
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.settings import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

class LLMProvider(ABC):
    """Abstract base for LLM providers."""
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> str:
        """Generate text from prompt."""
        pass

class OpenAIProvider(LLMProvider):
    """OpenAI API provider."""
    
    def __init__(self, api_key: str):
        import openai
        self.client = openai.AsyncOpenAI(api_key=api_key)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = await self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        return response.choices[0].message.content

class MockProvider(LLMProvider):
    """Mock provider for testing."""
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> str:
        return f"Mock response for: {prompt[:50]}..."

class LLMService:
    """Unified LLM service with provider abstraction."""
    
    def __init__(self):
        self.provider = self._initialize_provider()
    
    def _initialize_provider(self) -> LLMProvider:
        """Initialize the appropriate LLM provider."""
        if settings.openai_api_key:
            logger.info("Using OpenAI provider")
            return OpenAIProvider(settings.openai_api_key)
        else:
            logger.warning("No LLM API key configured, using mock provider")
            return MockProvider()
    
    async def summarize_content(
        self,
        content: str,
        max_length: int = 500
    ) -> Optional[str]:
        """Summarize content using LLM."""
        try:
            # Truncate content if too long
            if isinstance(content, bytes):
                content = content.decode('utf-8', errors='ignore')
            
            if len(content) > 10000:
                content = content[:10000] + "..."
            
            prompt = f"""
            Please provide a concise summary of the following content in about {max_length} words:
            
            {content}
            
            Summary:
            """
            
            summary = await self.provider.generate(
                prompt=prompt,
                system_prompt="You are a helpful assistant that creates concise, informative summaries.",
                temperature=0.5,
                max_tokens=max_length * 2  # Tokens != words, so give some buffer
            )
            
            return summary.strip()
            
        except Exception as e:
            logger.error(f"Error summarizing content: {e}")
            return None
    
    async def extract_topics(self, content: str) -> List[str]:
        """Extract main topics from content."""
        try:
            prompt = f"""
            Extract the main topics from this content. Return as a JSON array of strings.
            
            Content: {content[:2000]}
            
            Topics:
            """
            
            response = await self.provider.generate(
                prompt=prompt,
                system_prompt="You are a helpful assistant that extracts topics. Always return valid JSON arrays.",
                temperature=0.3,
                max_tokens=200
            )
            
            # Try to parse JSON response
            topics = json.loads(response)
            if isinstance(topics, list):
                return topics[:10]  # Limit to 10 topics
            
        except Exception as e:
            logger.error(f"Error extracting topics: {e}")
        
        return []

# Global instance
_llm_service = None

def get_llm_service() -> LLMService:
    """Get the global LLM service instance."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service