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

# Install cron, tmux, curl and other dependencies
RUN apt-get update && apt-get install -y \
    cron \
    bash \
    tmux \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install overmind
RUN curl -L https://github.com/DarthSim/overmind/releases/download/v2.5.1/overmind-v2.5.1-linux-amd64.gz | gunzip > /usr/local/bin/overmind && \
    chmod +x /usr/local/bin/overmind

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

# Add Procfile
COPY Procfile /app/

# Use overmind to manage processes
CMD ["overmind", "start"]
