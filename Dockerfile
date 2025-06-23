FROM python:3.13 AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_CACHE_DIR=/tmp/uv-cache

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies using uv
RUN uv sync --frozen --no-dev

FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install cron
RUN apt-get update && apt-get install -y cron && rm -rf /var/lib/apt/lists/*

# Copy uv from builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy the installed dependencies and project
COPY --from=builder /app/.venv .venv/
COPY . .

# Add crontab file
COPY crontab /etc/cron.d/scrapers-cron
RUN chmod 0644 /etc/cron.d/scrapers-cron && crontab /etc/cron.d/scrapers-cron

# Create log file for cron
RUN touch /var/log/cron.log

# Use uvx to run fastapi
CMD ["uvx", "--from", ".", "fastapi", "run", "app.main:app"]
