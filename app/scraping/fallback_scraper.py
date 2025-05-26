import requests
from bs4 import BeautifulSoup

def scrape_fallback(url: str):
    """
    Generic scraper for non-news websites.
    Removes boilerplate and extracts main content with a simple approach.
    """
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove obvious boilerplate tags
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()

        # Attempt to retrieve the title from the <title> tag
        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()

        # Get text from the remainder of the page
        content_text = soup.get_text(separator=" ", strip=True)

        return {
            "title": title,
            "author": None,
            "publication_date": None,
            "content": content_text
        }
    except Exception as e:
        print(f"Fallback scraper failed for {url}: {e}")
        return None