from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from .database import init_db
import uvicorn

app = FastAPI(title="News Aggregation & Summarization")

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    init_db()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include router endpoints - import after app creation to avoid circular imports
from .routers import articles, admin, podcasts
app.include_router(articles.router, prefix="/articles", tags=["Articles"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])
app.include_router(podcasts.router, prefix="/podcasts", tags=["Podcasts"])

@app.get("/")
def home():
    return {"message": "Welcome to the News App. Go to /articles/ to see today's articles."}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
