import time

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.core.db import init_db
from app.core.deps import AdminAuthRequired
from app.core.logging import setup_logging
from app.core.settings import get_settings
from app.routers import admin, api_content, auth, content, logs
from app.routers.api import scraper_configs

# Initialize
settings = get_settings()
logger = setup_logging()

# Create app
app = FastAPI(
    title=settings.app_name, version="2.0.0", description="Unified News Aggregation System"
)


# Exception handlers
def _serialize_validation_errors(errors: list) -> list:
    """Convert validation errors to JSON-serializable format."""
    serialized = []
    for error in errors:
        serialized_error = {
            "loc": error.get("loc"),
            "msg": str(error.get("msg", "")),
            "type": error.get("type"),
        }
        # Only include input if it's JSON-serializable
        if "input" in error:
            try:
                import json

                json.dumps(error["input"])
                serialized_error["input"] = error["input"]
            except (TypeError, ValueError):
                serialized_error["input"] = str(error["input"])
        serialized.append(serialized_error)
    return serialized


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle Pydantic validation errors with detailed logging.

    This catches 422 errors before they reach endpoint code.
    """
    # Get raw body for logging
    body = None
    try:
        body = await request.body()
        body_text = body.decode("utf-8")
    except Exception as e:
        body_text = f"<unable to read body: {e}>"

    # Log detailed validation error
    logger.error("=" * 80)
    logger.error("VALIDATION ERROR - Request failed Pydantic validation")
    logger.error(f"Path: {request.method} {request.url.path}")
    logger.error(f"Client: {request.client.host if request.client else 'unknown'}")
    logger.error(f"Headers: {dict(request.headers)}")
    logger.error(f"Raw body: {body_text}")
    logger.error("Validation errors:")
    for error in exc.errors():
        logger.error(f"  - Field: {error['loc']}, Error: {error['msg']}, Type: {error['type']}")
    logger.error("=" * 80)

    # Return standard FastAPI validation error response with serialized errors
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": _serialize_validation_errors(exc.errors()), "body": body_text},
    )


@app.exception_handler(AdminAuthRequired)
async def admin_auth_redirect_handler(_request: Request, exc: AdminAuthRequired):
    """Redirect to admin login page when admin authentication is required."""
    return RedirectResponse(url=exc.redirect_url, status_code=status.HTTP_303_SEE_OTHER)


# Request logging middleware with timing
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming HTTP requests with timing information."""
    start_time = time.perf_counter()

    logger.info(f">>> {request.method} {request.url.path}")
    logger.debug(f"    Headers: {dict(request.headers)}")
    logger.debug(f"    Client: {request.client.host if request.client else 'unknown'}")

    response = await call_next(request)

    duration_ms = (time.perf_counter() - start_time) * 1000

    # Add timing header to response
    response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

    # Log with severity based on duration
    method = request.method
    path = request.url.path
    status_code = response.status_code
    time_str = f"{duration_ms:.2f}ms"

    if duration_ms < 100:
        logger.info(f"<<< {method} {path} - {status_code} [{time_str}]")
    elif duration_ms < 500:
        logger.info(f"<<< {method} {path} - {status_code} [{time_str}] (slow)")
    else:
        logger.warning(f"<<< {method} {path} - {status_code} [{time_str}] (very slow)")

    return response


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
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(content.router)
app.include_router(admin.router)
app.include_router(logs.router)
app.include_router(api_content.router, prefix="/api/content")
app.include_router(scraper_configs.router, prefix="/api")


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
        uvicorn.run(app, host="0.0.0.0", port=8000, ssl_certfile=cert_file, ssl_keyfile=key_file)
    else:
        # Run without HTTPS
        uvicorn.run(app, host="0.0.0.0", port=8000)
