"""OpenAPI helpers for stable server-owned contract metadata."""

from __future__ import annotations

from collections.abc import Iterable

from fastapi.routing import APIRoute

IGNORED_PATH_TOKENS = {"api", "auth", "admin", "agent"}


def build_operation_id(route: APIRoute) -> str:
    """Build a stable operation ID from the route name and path."""
    if route.operation_id:
        return route.operation_id

    route_tokens = _tokenize_name(route.name or "operation")
    path_tokens = _tokenize_path(route.path)

    head, *tail = route_tokens
    qualifier_tokens: list[str] = []
    seen_tokens = {_normalize_token(token) for token in route_tokens}
    for token in path_tokens:
        normalized = _normalize_token(token)
        if normalized in seen_tokens:
            continue
        qualifier_tokens.append(token)
        seen_tokens.add(normalized)

    return _lower_camel_case([head, *qualifier_tokens, *tail])


def _tokenize_name(name: str) -> list[str]:
    return [token for token in name.replace("-", "_").split("_") if token]


def _tokenize_path(path: str) -> list[str]:
    tokens: list[str] = []
    for raw_segment in path.split("/"):
        segment = raw_segment.strip()
        if not segment or segment.startswith("{"):
            continue
        segment = segment.replace("-", "_")
        for token in segment.split("_"):
            if token and token not in IGNORED_PATH_TOKENS:
                tokens.append(token)
    return tokens


def _normalize_token(token: str) -> str:
    lowered = token.lower()
    if lowered.endswith("ies") and len(lowered) > 3:
        return lowered[:-3] + "y"
    if lowered.endswith("s") and len(lowered) > 3:
        return lowered[:-1]
    return lowered


def _lower_camel_case(tokens: Iterable[str]) -> str:
    cleaned = [token for token in tokens if token]
    if not cleaned:
        return "operation"

    head, *tail = cleaned
    return head.lower() + "".join(_upper_camel_case_token(token) for token in tail)


def _upper_camel_case_token(token: str) -> str:
    return "".join(part.capitalize() for part in token.split("_") if part)
