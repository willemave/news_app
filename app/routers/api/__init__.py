"""API content routers organized by responsibility.

This module exports a combined router that includes all API content endpoints,
organized into logical sub-routers:

- content_list: List, search, and unread counts
- content_detail: Individual content details and chat URLs
- read_status: Read/unread status management
- favorites: Favorites management
- content_actions: Content transformations (e.g., convert news to article)
"""

from fastapi import APIRouter

from app.routers.api import (
    content_actions,
    content_detail,
    content_list,
    favorites,
    read_status,
    submission,
)

# Create the main API router
router = APIRouter(
    tags=["content"],
    responses={404: {"description": "Not found"}},
)

# Include all sub-routers
# Content listing and discovery
router.include_router(content_list.router)

# Content detail and actions on individual items
router.include_router(content_detail.router)

# Read status management
router.include_router(read_status.router)

# Favorites management
router.include_router(favorites.router)

# Content transformations and actions
router.include_router(content_actions.router)

# User submissions
router.include_router(submission.router)

__all__ = ["router"]
