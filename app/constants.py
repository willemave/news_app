"""
Constants for the podcast pipeline system.
"""

# Worker type constants for checkout mechanism
WORKER_DOWNLOADER = "downloader"
WORKER_TRANSCRIBER = "transcriber"
WORKER_SUMMARIZER = "summarizer"

# Checkout timeout in minutes
DEFAULT_CHECKOUT_TIMEOUT_MINUTES = 30

# Pipeline polling interval in seconds
DEFAULT_POLLING_INTERVAL_SECONDS = 10

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
