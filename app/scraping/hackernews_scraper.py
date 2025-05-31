import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict, Optional
from ..database import SessionLocal
from ..models import Articles, Summaries, ArticleStatus
from ..llm import summarize_article

def fetch_hackernews_homepage() -> str:
    """
    Fetch the HTML content of the HackerNews homepage.
    Returns the raw HTML content.
    """
    try:
        response = requests.get("https://news.ycombinator.com/", timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error fetching HackerNews homepage: {e}")
        return ""

def extract_article_links(homepage_html: str) -> List[str]:
    """
    Parse the HackerNews homepage HTML and extract article URLs.
    Returns a list of article URLs.
    """
    try:
        soup = BeautifulSoup(homepage_html, "html.parser")
        article_links = []
        
        # HackerNews structure: look for links with class "titleline"
        titleline_elements = soup.find_all("span", class_="titleline")
        
        for titleline in titleline_elements:
            link_element = titleline.find("a")
            if link_element and link_element.get("href"):
                href = link_element.get("href")
                
                # Handle relative URLs (HN internal links start with "item?id=")
                if href.startswith("item?id="):
                    # Skip HN internal discussion links
                    continue
                elif href.startswith("http"):
                    # External link - this is what we want
                    article_links.append(href)
                
        return article_links
    except Exception as e:
        print(f"Error extracting article links: {e}")
        return []

def scrape_article_content(article_url: str) -> Optional[Dict[str, str]]:
    """
    Scrape the content of an individual article URL.
    Returns a dictionary with url, title, and raw_content, or None if failed.
    """
    try:
        response = requests.get(article_url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Remove obvious boilerplate tags
        for script in soup(["script", "style", "nav", "footer", "header", "aside"]):
            script.decompose()

        # Extract title
        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        
        # Try to find main content areas (common patterns)
        content_selectors = [
            "article",
            "main",
            ".content",
            ".post-content",
            ".entry-content",
            ".article-content",
            "#content",
            ".story-body"
        ]
        
        content_text = ""
        for selector in content_selectors:
            content_element = soup.select_one(selector)
            if content_element:
                content_text = content_element.get_text(separator=" ", strip=True)
                break
        
        # If no specific content area found, get all text
        if not content_text:
            content_text = soup.get_text(separator=" ", strip=True)
        
        # Basic content validation - ensure we have substantial content
        if len(content_text.strip()) < 100:
            print(f"Content too short for {article_url}")
            return None

        return {
            "url": article_url,
            "title": title,
            "raw_content": content_text
        }
    except Exception as e:
        print(f"Error scraping article {article_url}: {e}")
        return None

def process_hackernews_articles() -> Dict[str, int]:
    """
    Main function to process HackerNews articles:
    1. Fetch homepage
    2. Extract article links
    3. Scrape each article
    4. Summarize content
    5. Store in database
    
    Returns a dictionary with processing statistics.
    """
    stats = {
        "total_links": 0,
        "successful_scrapes": 0,
        "successful_summaries": 0,
        "errors": 0
    }
    
    print("Starting HackerNews scraping process...")
    
    # Fetch homepage
    homepage_html = fetch_hackernews_homepage()
    if not homepage_html:
        print("Failed to fetch HackerNews homepage")
        return stats
    
    # Extract article links
    article_links = extract_article_links(homepage_html)
    stats["total_links"] = len(article_links)
    print(f"Found {len(article_links)} article links")
    
    # Get database session
    db = SessionLocal()
    
    try:
        for i, article_url in enumerate(article_links, 1):
            print(f"Processing article {i}/{len(article_links)}: {article_url}")
            
            # Check if article already exists
            existing_article = db.query(Articles).filter(Articles.url == article_url).first()
            if existing_article:
                print(f"Article already exists, skipping: {article_url}")
                continue
            
            # Scrape article content
            article_data = scrape_article_content(article_url)
            if not article_data:
                stats["errors"] += 1
                continue
            
            stats["successful_scrapes"] += 1
            
            # Create Article record
            article = Articles(
                title=article_data["title"],
                url=article_data["url"],
                raw_content=article_data["raw_content"],
                scraped_date=datetime.utcnow(),
                status=ArticleStatus.scraped
            )
            
            db.add(article)
            db.flush()  # Get the article ID
            
            # Generate summary
            try:
                summaries = summarize_article(article_data["raw_content"])

                # Create Summary record
                summary = Summaries(
                    article_id=article.id,
                    short_summary=summaries["short"],
                    detailed_summary=summaries["detailed"],  # Using same summary for both for now
                    summary_date=datetime.utcnow()
                )
                
                db.add(summary)
                
                # Update article status to processed
                article.status = ArticleStatus.processed
                
                stats["successful_summaries"] += 1
                print(f"Successfully processed and summarized: {article_data['title']}")
                
            except Exception as e:
                print(f"Error generating summary for {article_url}: {e}")
                stats["errors"] += 1
                # Keep article as scraped even if summary fails
            
            # Commit after each article to avoid losing progress
            db.commit()
    
    except Exception as e:
        print(f"Error in process_hackernews_articles: {e}")
        db.rollback()
        stats["errors"] += 1
    
    finally:
        db.close()
    
    print(f"HackerNews scraping completed. Stats: {stats}")
    return stats
