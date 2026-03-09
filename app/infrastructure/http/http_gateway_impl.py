"""Infrastructure implementation helpers for the HTTP gateway."""

from __future__ import annotations

from app.http_client.robust_http_client import RobustHttpClient
from app.services.http import HttpService, get_http_service


def build_http_gateway_dependencies() -> tuple[HttpService, RobustHttpClient]:
    """Build concrete HTTP client dependencies for the application gateway."""
    return get_http_service(), RobustHttpClient()
