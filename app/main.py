from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.db import init_db
from app.core.logging import setup_logging
from app.core.settings import get_settings
from app.routers import admin, api_content, content, logs

# Initialize
settings = get_settings()
logger = setup_logging()

# Create app
app = FastAPI(
    title=settings.app_name, version="2.0.0", description="Unified News Aggregation System"
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
app.include_router(admin.router)
app.include_router(logs.router)
app.include_router(api_content.router, prefix="/api/content")


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
    import os
    import uvicorn

    # Check if SSL certificates exist
    cert_file = "certs/cert.pem"
    key_file = "certs/key.pem"
    
    if os.path.exists(cert_file) and os.path.exists(key_file):
        # Run with HTTPS
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            ssl_certfile=cert_file,
            ssl_keyfile=key_file
        )
    else:
        # Run without HTTPS
        uvicorn.run(app, host="0.0.0.0", port=8000)
