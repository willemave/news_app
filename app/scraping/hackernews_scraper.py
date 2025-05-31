import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from ..queue import process_link_task

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


def process_hackernews_articles() -> Dict[str, int]:
    """
    Main function to process HackerNews articles:
    1. Fetch homepage
    2. Extract article links
    3. Add links to processing queue
    
    Returns a dictionary with processing statistics.
    """
    stats = {
        "total_links": 0,
        "queued_links": 0,
        "errors": 0
    }
    
    print("Starting HackerNews link discovery...")
    
    # Fetch homepage
    homepage_html = fetch_hackernews_homepage()
    if not homepage_html:
        print("Failed to fetch HackerNews homepage")
        return stats
    
    # Extract article links
    article_links = extract_article_links(homepage_html)
    stats["total_links"] = len(article_links)
    print(f"Found {len(article_links)} article links")
    
    # Queue each link for processing
    for i, article_url in enumerate(article_links, 1):
        print(f"Queuing link {i}/{len(article_links)}: {article_url}")
        
        try:
            # Add link to processing queue
            process_link_task(article_url, "hackernews")
            stats["queued_links"] += 1
            print(f"Queued link for processing: {article_url}")
            
        except Exception as e:
            print(f"Error queuing link {article_url}: {e}")
            stats["errors"] += 1
    
    print(f"HackerNews link discovery completed. Stats: {stats}")
    return stats
