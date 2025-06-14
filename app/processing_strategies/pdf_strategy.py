import io
from typing import Optional, Dict, Any
import PyPDF2
import httpx

from app.processing_strategies.base_strategy import UrlProcessorStrategy
from app.http_client.robust_http_client import RobustHttpClient
from app.core.logging import get_logger

logger = get_logger(__name__)

class PdfProcessorStrategy(UrlProcessorStrategy):
    """Strategy for processing PDF documents."""
    
    def __init__(self, http_client: RobustHttpClient):
        super().__init__(http_client)
    
    def can_handle_url(self, url: str, response_headers: Optional[httpx.Headers] = None) -> bool:
        """Check if this strategy can handle the given URL."""
        # Check URL extension
        if url.lower().endswith('.pdf'):
            return True
        
        # Check content type
        if response_headers:
            content_type = response_headers.get('content-type', '').lower()
            return 'application/pdf' in content_type
        
        # Check for arXiv PDF URLs
        if 'arxiv.org/pdf/' in url.lower():
            return True
        
        return False
    
    def preprocess_url(self, url: str) -> str:
        """Preprocess PDF URLs (e.g., convert arXiv abstract to PDF)."""
        # Convert arXiv abstract URLs to PDF URLs
        if 'arxiv.org/abs/' in url:
            return url.replace('/abs/', '/pdf/') + '.pdf'
        
        return url
    
    def download_content(self, url: str) -> bytes:
        """Download PDF content from the given URL."""
        logger.info(f"PdfStrategy: Downloading PDF content from {url}")
        response = self.http_client.get(url)
        logger.info(f"PdfStrategy: Successfully downloaded PDF from {url}. Final URL: {response.url}")
        return response.content  # Returns PDF as bytes
    
    def extract_data(self, content: bytes, url: str) -> Dict[str, Any]:
        """Extract data from PDF content."""
        logger.info(f"PdfStrategy: Extracting data from PDF content for URL: {url}")
        
        # Extract text from PDF
        text = self._extract_pdf_text(content)
        
        if not text:
            logger.warning(f"PdfStrategy: Failed to extract text from PDF {url}")
            return {
                "title": "PDF Extraction Failed",
                "text_content": "",
                "content_type": "pdf",
                "final_url_after_redirects": url,
            }
        
        # Try to extract title from first lines
        lines = text.strip().split('\n')
        title = lines[0][:200] if lines else "PDF Document"
        
        logger.info(f"PdfStrategy: Successfully extracted data for {url}. Title: {title[:50]}...")
        return {
            "title": title,
            "author": None,  # Could be enhanced to extract from PDF metadata
            "publication_date": None,
            "text_content": text,
            "content_type": "pdf",
            "final_url_after_redirects": url,
        }
    
    def prepare_for_llm(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare extracted PDF data for LLM processing."""
        logger.info(f"PdfStrategy: Preparing data for LLM for URL: {extracted_data.get('final_url_after_redirects')}")
        text_content = extracted_data.get("text_content", "")
        
        return {
            "content_to_filter": text_content,
            "content_to_summarize": text_content,
            "is_pdf": True
        }
    
    def _extract_pdf_text(self, pdf_content: bytes) -> str:
        """Extract text from PDF bytes."""
        try:
            pdf_file = io.BytesIO(pdf_content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            text_parts = []
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text_parts.append(page.extract_text())
            
            return '\n'.join(text_parts)
        except Exception as e:
            logger.error(f"Failed to extract PDF text: {e}")
            return ""