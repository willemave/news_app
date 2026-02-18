"""API endpoints for content with OpenAPI documentation.

This module provides backward compatibility by importing the refactored
router structure from app.routers.api. All endpoint implementations have
been moved to specialized modules:

- app.routers.api.models: Pydantic request/response models
- app.routers.api.content_list: List, search, unread counts
- app.routers.api.content_detail: Content detail and chat URLs
- app.routers.api.read_status: Read/unread operations
- app.routers.api.favorites: Favorites management
- app.routers.api.content_actions: Content transformations

This file now serves as a thin compatibility layer for existing imports.
"""

from app.routers.api import router

# Re-export models for backward compatibility
from app.routers.api.models import (
    BulkMarkReadRequest,
    ChatGPTUrlResponse,
    ContentDetailResponse,
    ContentDiscussionResponse,
    ContentListResponse,
    ContentSummaryResponse,
    ConvertNewsResponse,
    RecordContentInteractionRequest,
    RecordContentInteractionResponse,
    UnreadCountsResponse,
)

__all__ = [
    "router",
    "ContentSummaryResponse",
    "ContentListResponse",
    "ContentDetailResponse",
    "ContentDiscussionResponse",
    "BulkMarkReadRequest",
    "ChatGPTUrlResponse",
    "UnreadCountsResponse",
    "ConvertNewsResponse",
    "RecordContentInteractionRequest",
    "RecordContentInteractionResponse",
]
