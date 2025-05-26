# News Aggregation & Summarization App

This project is a FastAPI-based web application that:
1. Fetches links from Raindrop.io and multiple RSS feeds.
2. Scrapes and stores article content (HTML or PDF).
3. Summarizes approved content with an LLM.
4. Displays daily links via a web interface (HTMX-enabled).

## Quickstart

1. Clone this repository.
2. Create and activate a Python virtual environment.
3. \`pip install -r requirements.txt\`
4. Run the FastAPI app:
   \`\`\`
   uvicorn app.main:app --reload
   \`\`\`
5. (Optional) Schedule \`cron/daily_ingest.py\` to run daily (or trigger manually).

## Project Structure

- \`app/\`: Main FastAPI application
- \`cron/\`: Scripts for scheduled jobs
- \`templates/\`: Jinja2/HTMX HTML templates
- \`static/\`: Static files (CSS/JS)
