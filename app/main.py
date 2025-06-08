from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from .routers import articles, admin, podcasts
from .database import init_db
import markdown
from markupsafe import Markup
import uvicorn

app = FastAPI(title="News Aggregation & Summarization")

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    init_db()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Add markdown filter to Jinja2
def markdown_filter(text):
    """Convert markdown text to HTML."""
    if not text:
        return ""
    md = markdown.Markdown(extensions=['fenced_code', 'tables', 'nl2br'])
    return Markup(md.convert(text))

templates.env.filters['markdown'] = markdown_filter

# Include router endpoints
app.include_router(articles.router, prefix="/articles", tags=["Articles"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])
app.include_router(podcasts.router, prefix="/podcasts", tags=["Podcasts"])

@app.get("/")
def home():
    return {"message": "Welcome to the News App. Go to /articles/ to see today's articles."}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
