#!/bin/bash

# Navigate to the project directory
cd /Users/willem/Development/news_app

# Activate the virtual environment
source .venv/bin/activate

# Start the server
uvicorn app.main:app --reload