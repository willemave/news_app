#!/bin/bash

# Check if virtual environment exists and activate it
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "Installing uv package installer..."
    pip install uv
fi

# Check if requirements are installed
if ! command -v uvicorn &> /dev/null; then
    echo "Installing requirements with uv..."
    uv pip install -r requirements.txt
fi

# Check for required environment variables
if [ ! -f .env ]; then
    echo "Warning: .env file not found. Make sure to set up your environment variables."
fi

# Start the FastAPI server
echo "Starting the News App server..."
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 