import re
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup
from datetime import datetime

from app.strategies.base import ProcessingStrategy
from app.models.metadata import ProcessingResult, ContentType
from app.core.logging import get_logger

logger = get_logger(__name__)

class HtmlStrategy(ProcessingStrategy):
    """Strategy for processing standard HTML content."""
    
    def can_handle(self, url: str, headers: Optional[Dict[str, str]] = None) -> bool:
        # Skip if it's a PDF URL
        if self.is_pdf_url(url):
            return False
        
        # Skip media content
        if self.is_media_content(headers):
            return False
        
        # Check content type if available
        if headers:
            content_type = headers.get('content-type', '').lower()
            return 'text/html' in content_type
        
        # Default to true for unknown content
        return True
    
    async def process(self, url: str, content: Optional[str] = None) -> ProcessingResult:
        """Process HTML content."""
        try:
            if not content:
                return ProcessingResult(
                    success=False,
                    content_type=ContentType.ARTICLE,
                    error_message="No content provided"
                )
            
            # Parse HTML
            soup = BeautifulSoup(content, 'html.parser')
            
            # Extract title
            title = self._extract_title(soup)
            
            # Extract main content
            article_text = self._extract_article_text(soup)
            
            # Extract metadata
            metadata = {
                'content': article_text,
                'author': self._extract_author(soup),
                'publish_date': self._extract_publish_date(soup),
                'source_type': 'html',
                'word_count': len(article_text.split()) if article_text else 0,
                'reading_time_minutes': max(1, len(article_text.split()) // 200) if article_text else 0
            }
            
            # Extract internal links
            internal_links = self.extract_internal_links(content, url)
            
            return ProcessingResult(
                success=True,
                content_type=ContentType.ARTICLE,
                title=title,
                metadata=metadata,
                internal_links=internal_links
            )
            
        except Exception as e:
            logger.error(f"Error processing HTML from {url}: {e}")
            return ProcessingResult(
                success=False,
                content_type=ContentType.ARTICLE,
                error_message=str(e)
            )
    
    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract title from HTML."""
        # Try multiple strategies
        strategies = [
            lambda: soup.find('title').get_text(strip=True) if soup.find('title') else None,
            lambda: soup.find('h1').get_text(strip=True) if soup.find('h1') else None,
            lambda: soup.find('meta', {'property': 'og:title'})['content'] if soup.find('meta', {'property': 'og:title'}) else None,
            lambda: soup.find('meta', {'name': 'twitter:title'})['content'] if soup.find('meta', {'name': 'twitter:title'}) else None,
        ]
        
        for strategy in strategies:
            try:
                title = strategy()
                if title:
                    return title[:500]  # Limit length
            except:
                continue
        
        return None
    
    def _extract_article_text(self, soup: BeautifulSoup) -> str:
        """Extract main article text from HTML."""
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Try to find article content
        article_selectors = [
            'article',
            'main',
            '[role="main"]',
            '.post-content',
            '.entry-content',
            '.content',
            '#content'
        ]
        
        for selector in article_selectors:
            element = soup.select_one(selector)
            if element:
                return element.get_text(separator=' ', strip=True)
        
        # Fallback to body
        body = soup.find('body')
        if body:
            return body.get_text(separator=' ', strip=True)
        
        return soup.get_text(separator=' ', strip=True)
    
    def _extract_author(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract author from HTML."""
        author_selectors = [
            ('meta', {'name': 'author'}),
            ('meta', {'property': 'article:author'}),
            ('span', {'class': 'author'}),
            ('div', {'class': 'author'}),
            ('a', {'rel': 'author'})
        ]
        
        for tag, attrs in author_selectors:
            element = soup.find(tag, attrs)
            if element:
                if tag == 'meta':
                    return element.get('content', '').strip()
                else:
                    return element.get_text(strip=True)
        
        return None
    
    def _extract_publish_date(self, soup: BeautifulSoup) -> Optional[datetime]:
        """Extract publish date from HTML."""
        date_selectors = [
            ('meta', {'property': 'article:published_time'}),
            ('meta', {'name': 'publish_date'}),
            ('time', {'datetime': True}),
            ('span', {'class': 'date'}),
            ('div', {'class': 'date'})
        ]
        
        for tag, attrs in date_selectors:
            element = soup.find(tag, attrs)
            if element:
                date_str = None
                if tag == 'meta':
                    date_str = element.get('content')
                elif tag == 'time':
                    date_str = element.get('datetime')
                else:
                    date_str = element.get_text(strip=True)
                
                if date_str:
                    # Try to parse the date (add more formats as needed)
                    for fmt in ['%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%SZ']:
                        try:
                            return datetime.strptime(date_str[:19], fmt)
                        except:
                            continue
        
        return None