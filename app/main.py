from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.core.settings import get_settings
from app.core.logging import setup_logging
from app.core.db import init_db
from app.routers import content, logs

# Initialize
settings = get_settings()
logger = setup_logging()

# Create app
app = FastAPI(
    title=settings.app_name,
    version="2.0.0",
    description="Unified News Aggregation System"
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
app.include_router(content.router)
app.include_router(logs.router)

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("Starting up...")
    init_db()
    logger.info("Database initialized")

# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": settings.app_name}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)