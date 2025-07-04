#!/bin/bash
set -e

echo "Starting application..."
echo "Current directory: $(pwd)"
echo "Checking for Procfile..."
ls -la Procfile || echo "Procfile not found!"

echo "Checking Python environment..."
.venv/bin/python --version || echo "Python not found in .venv!"

# Ensure Playwright browsers are installed
echo "Checking Playwright browsers..."
if ! .venv/bin/python -m playwright install --dry-run chromium 2>&1 | grep -q "chromium.*is already installed"; then
    echo "Installing Playwright browsers..."
    .venv/bin/python -m playwright install chromium || echo "Warning: Could not install Playwright browsers"
fi

# Increase shared memory for Chrome/Chromium
echo "Setting up shared memory..."
mount -o remount,size=2G /dev/shm || echo "Could not remount /dev/shm (may not have permissions)"

echo "Starting overmind with explicit Procfile path..."
exec overmind start -f /app/Procfile