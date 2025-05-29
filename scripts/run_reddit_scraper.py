import json
from app.scraping.reddit import fetch_frontpage_posts


def main(limit: int = 5):
    """Fetch and print summaries for Reddit front page posts."""
    posts = fetch_frontpage_posts(limit=limit)
    print(json.dumps(posts, indent=2))


if __name__ == "__main__":
    main()
