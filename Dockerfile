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

# Install cron, tmux, curl and Playwright dependencies
RUN apt-get update && apt-get install -y \
    cron \
    bash \
    tmux \
    curl \
    # Playwright dependencies
    wget \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libc6 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libexpat1 \
    libfontconfig1 \
    libgbm1 \
    libgcc1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libstdc++6 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    lsb-release \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Install overmind
RUN curl -L https://github.com/DarthSim/overmind/releases/download/v2.5.1/overmind-v2.5.1-linux-amd64.gz | gunzip > /usr/local/bin/overmind && \
    chmod +x /usr/local/bin/overmind

# Copy uv from builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy the installed dependencies and project
COPY --from=builder /app/.venv .venv/
COPY . .

# Install Playwright browsers with dependencies in default location
RUN .venv/bin/python -m playwright install chromium --with-deps

# Create directories for Chrome to avoid permission issues
RUN mkdir -p /tmp/.X11-unix && chmod 1777 /tmp/.X11-unix

# Add crontab file
COPY crontab /etc/cron.d/scrapers-cron
RUN chmod 0644 /etc/cron.d/scrapers-cron && crontab /etc/cron.d/scrapers-cron

# Create log file for cron
RUN touch /var/log/cron.log

# Add Procfile
COPY Procfile /app/

# Add startup script
COPY start.sh /app/
RUN chmod +x /app/start.sh

# Use startup script to manage processes
CMD ["/app/start.sh"]
