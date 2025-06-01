from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from .routers import articles, admin


app = FastAPI(title="News Aggregation & Summarization")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Include router endpoints
app.include_router(articles.router, prefix="/articles", tags=["Articles"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])

@app.get("/")
def home():
    return {"message": "Welcome to the News App. Go to /articles/ to see today's articles."}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
