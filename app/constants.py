"""Application-wide constants and defaults."""

# Default LLM models
TWEET_SUGGESTION_MODEL = "google-gla:gemini-3-pro-preview"

# LLM provider models for tweet suggestions
TWEET_MODELS = {
    "google": "google-gla:gemini-3-pro-preview",
    "openai": "openai:gpt-4o",
    "anthropic": "anthropic:claude-sonnet-4-5-20250929",
}

# Worker type constants for checkout mechanism
WORKER_DOWNLOADER = "downloader"
WORKER_TRANSCRIBER = "transcriber"
WORKER_SUMMARIZER = "summarizer"

# Checkout timeout in minutes
DEFAULT_CHECKOUT_TIMEOUT_MINUTES = 30

# Pipeline polling interval in seconds
DEFAULT_POLLING_INTERVAL_SECONDS = 10

# Source label applied to user-submitted items
SELF_SUBMISSION_SOURCE = "self submission"

# Worker concurrency limits
DEFAULT_DOWNLOADER_CONCURRENCY = 5
DEFAULT_TRANSCRIBER_CONCURRENCY = 2
DEFAULT_SUMMARIZER_CONCURRENCY = 2

# Aggregate content platforms that should skip LLM summaries
AGGREGATE_PLATFORMS = {"twitter", "techmeme"}


# Worker ID format: {worker_type}_{instance_id}_{pid}
def generate_worker_id(worker_type: str, instance_id: str = "1") -> str:
    """Generate a unique worker ID for checkout mechanism."""
    import os

    pid = os.getpid()
    return f"{worker_type}_{instance_id}_{pid}"
