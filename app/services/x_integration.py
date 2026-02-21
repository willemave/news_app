"""Service layer for user-specific X integration state and sync."""

from __future__ import annotations

import base64
import hashlib
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.settings import get_settings
from app.models.content_submission import SubmitContentRequest
from app.models.schema import UserIntegrationConnection, UserIntegrationSyncState
from app.models.user import User
from app.services.content_submission import submit_user_content
from app.services.token_crypto import decrypt_token, encrypt_token
from app.services.twitter_share import canonical_tweet_url
from app.services.x_api import (
    X_DEFAULT_SCOPES,
    build_oauth_authorize_url,
    exchange_oauth_code,
    fetch_bookmarks,
    get_authenticated_user,
    refresh_oauth_token,
)

logger = get_logger(__name__)

X_PROVIDER = "x"
OAUTH_PENDING_KEY = "oauth_pending"
OAUTH_PENDING_TTL_MINUTES = 20
TOKEN_EXPIRY_SKEW_SECONDS = 60
BOOKMARK_SYNC_MAX_PAGES = 5
BOOKMARK_SYNC_PAGE_SIZE = 100
USERNAME_REGEX = re.compile(r"^[A-Za-z0-9_]{1,15}$")


@dataclass(frozen=True)
class XConnectionView:
    """Normalized connection payload for API responses."""

    provider: str
    connected: bool
    is_active: bool
    provider_user_id: str | None
    provider_username: str | None
    scopes: list[str]
    last_synced_at: datetime | None
    last_status: str | None
    last_error: str | None
    twitter_username: str | None


@dataclass(frozen=True)
class BookmarkSyncSummary:
    """Summary for one bookmark sync run."""

    status: str
    fetched: int
    created: int
    reused: int
    newest_bookmark_id: str | None


def normalize_twitter_username(username: str | None) -> str | None:
    """Normalize user-provided X username to canonical form.

    Args:
        username: Raw username value from request/UI.

    Returns:
        Lowercased username without leading @, or None when empty.

    Raises:
        ValueError: If the non-empty input is not a valid username.
    """
    if username is None:
        return None
    cleaned = username.strip()
    if not cleaned:
        return None
    if cleaned.startswith("@"):
        cleaned = cleaned[1:]
    cleaned = cleaned.strip()
    if not cleaned:
        return None
    if not USERNAME_REGEX.fullmatch(cleaned):
        raise ValueError("Twitter username must be 1-15 chars (letters, numbers, underscore)")
    return cleaned.lower()


def is_x_oauth_configured() -> bool:
    """Return whether required X OAuth configuration is available."""
    settings = get_settings()
    return bool(
        (settings.x_client_id or "").strip()
        and (settings.x_oauth_redirect_uri or "").strip()
        and (settings.x_token_encryption_key or "").strip()
    )


def has_active_x_connection(db: Session, user_id: int) -> bool:
    """Return True when a user has an active X bookmark connection."""
    connection = _get_connection(db, user_id=user_id)
    return bool(connection and connection.is_active and connection.access_token_encrypted)


def get_x_user_access_token(db: Session, *, user_id: int) -> str | None:
    """Return a valid decrypted user access token when connection is active."""
    connection = _get_connection(db, user_id=user_id)
    if not connection or not connection.is_active:
        return None
    try:
        return _ensure_valid_access_token(db, connection)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Unable to get user access token for X connection",
            extra={
                "component": "x_integration",
                "operation": "get_access_token",
                "item_id": str(user_id),
                "context_data": {"error": str(exc)},
            },
        )
        return None


def get_x_connection_view(db: Session, user: User) -> XConnectionView:
    """Build a normalized X connection view for API responses."""
    connection = _get_connection(db, user_id=user.id)
    sync_state = _get_sync_state(db, connection_id=connection.id) if connection else None
    connected = bool(connection and connection.is_active and connection.access_token_encrypted)

    return XConnectionView(
        provider=X_PROVIDER,
        connected=connected,
        is_active=bool(connection and connection.is_active),
        provider_user_id=connection.provider_user_id if connection else None,
        provider_username=connection.provider_username if connection else None,
        scopes=_normalize_scopes(connection.scopes if connection else None),
        last_synced_at=sync_state.last_synced_at if sync_state else None,
        last_status=sync_state.last_status if sync_state else None,
        last_error=sync_state.last_error if sync_state else None,
        twitter_username=user.twitter_username,
    )


def start_x_oauth(
    db: Session,
    *,
    user: User,
    twitter_username: str | None = None,
) -> tuple[str, str, list[str]]:
    """Start X OAuth flow and persist PKCE/state metadata."""
    if not is_x_oauth_configured():
        raise ValueError(
            "X OAuth is not configured. Set X_CLIENT_ID, X_OAUTH_REDIRECT_URI, and "
            "X_TOKEN_ENCRYPTION_KEY."
        )

    normalized_username = normalize_twitter_username(twitter_username)
    if normalized_username is not None:
        user.twitter_username = normalized_username

    connection = _get_or_create_connection(db, user_id=user.id)
    state = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = _build_pkce_code_challenge(code_verifier)
    scopes = list(X_DEFAULT_SCOPES)

    metadata = dict(connection.connection_metadata or {})
    metadata[OAUTH_PENDING_KEY] = {
        "state": state,
        "code_verifier": code_verifier,
        "created_at": _now_utc_iso(),
    }

    connection.scopes = scopes
    connection.connection_metadata = metadata
    db.commit()

    authorize_url = build_oauth_authorize_url(
        state=state,
        code_challenge=code_challenge,
        scopes=scopes,
    )
    return authorize_url, state, scopes


def exchange_x_oauth(
    db: Session,
    *,
    user: User,
    code: str,
    state: str,
) -> XConnectionView:
    """Finalize X OAuth code exchange and persist encrypted tokens."""
    connection = _get_connection(db, user_id=user.id)
    if not connection:
        raise ValueError("OAuth flow not initialized. Start OAuth first.")

    metadata = dict(connection.connection_metadata or {})
    pending = metadata.get(OAUTH_PENDING_KEY)
    if not isinstance(pending, dict):
        raise ValueError("OAuth flow expired or missing. Start OAuth again.")

    expected_state = pending.get("state")
    code_verifier = pending.get("code_verifier")
    created_at = pending.get("created_at")
    if not isinstance(expected_state, str) or not isinstance(code_verifier, str):
        raise ValueError("Invalid OAuth pending state. Start OAuth again.")
    if expected_state != state:
        raise ValueError("Invalid OAuth state")
    if _pending_state_expired(created_at):
        raise ValueError("OAuth flow expired. Start OAuth again.")

    token = exchange_oauth_code(code=code, code_verifier=code_verifier)
    me = get_authenticated_user(access_token=token.access_token)

    metadata.pop(OAUTH_PENDING_KEY, None)
    metadata["connected_at"] = _now_utc_iso()

    connection.provider_user_id = me.id
    connection.provider_username = me.username
    connection.access_token_encrypted = encrypt_token(token.access_token)
    connection.refresh_token_encrypted = (
        encrypt_token(token.refresh_token) if token.refresh_token else None
    )
    connection.token_expires_at = _expires_at_from_seconds(token.expires_in)
    connection.scopes = token.scopes or list(X_DEFAULT_SCOPES)
    connection.is_active = True
    connection.connection_metadata = metadata

    if me.username:
        user.twitter_username = normalize_twitter_username(me.username)

    sync_state = _get_or_create_sync_state(db, connection_id=connection.id)
    if not sync_state.last_status:
        sync_state.last_status = "connected"
    sync_state.last_error = None

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        logger.exception(
            "Failed to save X OAuth exchange due to integrity error",
            extra={
                "component": "x_integration",
                "operation": "oauth_exchange",
                "item_id": str(user.id),
                "context_data": {"error": str(exc)},
            },
        )
        raise ValueError("This X account is already linked to another user.") from exc

    db.refresh(user)
    return get_x_connection_view(db, user)


def disconnect_x_connection(db: Session, *, user: User) -> XConnectionView:
    """Disable an X connection and clear stored tokens."""
    connection = _get_connection(db, user_id=user.id)
    if connection:
        metadata = dict(connection.connection_metadata or {})
        metadata.pop(OAUTH_PENDING_KEY, None)
        metadata["disconnected_at"] = _now_utc_iso()

        connection.is_active = False
        connection.access_token_encrypted = None
        connection.refresh_token_encrypted = None
        connection.token_expires_at = None
        connection.connection_metadata = metadata

        sync_state = _get_or_create_sync_state(db, connection_id=connection.id)
        sync_state.last_status = "disconnected"
        sync_state.last_error = None
        sync_state.last_synced_at = _now_naive_utc()
        db.commit()

    return get_x_connection_view(db, user)


def sync_x_bookmarks_for_user(db: Session, *, user_id: int) -> BookmarkSyncSummary:
    """Sync new bookmarks for a user's connected X account."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError(f"User {user_id} not found")

    connection = _get_connection(db, user_id=user.id)
    if not connection or not connection.is_active:
        return BookmarkSyncSummary(
            status="not_connected",
            fetched=0,
            created=0,
            reused=0,
            newest_bookmark_id=None,
        )

    sync_state = _get_or_create_sync_state(db, connection_id=connection.id)

    try:
        access_token = _ensure_valid_access_token(db, connection)
        provider_user_id = _ensure_provider_user_id(
            db,
            user=user,
            connection=connection,
            access_token=access_token,
        )

        last_synced_id = sync_state.last_synced_item_id
        newest_seen_id: str | None = None
        fetched = 0
        collected_new: list[str] = []
        next_token: str | None = None
        reached_previous_sync = False

        for _ in range(BOOKMARK_SYNC_MAX_PAGES):
            page = fetch_bookmarks(
                access_token=access_token,
                user_id=provider_user_id,
                pagination_token=next_token,
                max_results=BOOKMARK_SYNC_PAGE_SIZE,
            )
            if page.tweets and newest_seen_id is None:
                newest_seen_id = page.tweets[0].id

            fetched += len(page.tweets)
            if not page.tweets:
                break

            for tweet in page.tweets:
                if last_synced_id and tweet.id == last_synced_id:
                    reached_previous_sync = True
                    break
                collected_new.append(tweet.id)

            if reached_previous_sync or not page.next_token:
                break
            next_token = page.next_token

        created = 0
        reused = 0
        for tweet_id in reversed(collected_new):
            result = submit_user_content(
                db,
                SubmitContentRequest(
                    url=canonical_tweet_url(tweet_id),
                    platform="twitter",
                ),
                user,
                submitted_via="x_bookmarks",
            )
            if result.already_exists:
                reused += 1
            else:
                created += 1

        sync_state.last_synced_at = _now_naive_utc()
        sync_state.last_status = "success"
        sync_state.last_error = None
        if newest_seen_id:
            sync_state.last_synced_item_id = newest_seen_id
        sync_state.cursor = None
        sync_state.sync_metadata = {
            "fetched": fetched,
            "created": created,
            "reused": reused,
            "new_count": len(collected_new),
            "newest_bookmark_id": newest_seen_id,
        }
        db.commit()

        return BookmarkSyncSummary(
            status="success",
            fetched=fetched,
            created=created,
            reused=reused,
            newest_bookmark_id=newest_seen_id,
        )

    except Exception as exc:  # noqa: BLE001
        sync_state.last_synced_at = _now_naive_utc()
        sync_state.last_status = "failed"
        sync_state.last_error = str(exc)[:2000]
        db.commit()
        raise


def _ensure_provider_user_id(
    db: Session,
    *,
    user: User,
    connection: UserIntegrationConnection,
    access_token: str,
) -> str:
    provider_user_id = (connection.provider_user_id or "").strip()
    if provider_user_id:
        return provider_user_id

    me = get_authenticated_user(access_token=access_token)
    connection.provider_user_id = me.id
    connection.provider_username = me.username
    if me.username and not user.twitter_username:
        user.twitter_username = normalize_twitter_username(me.username)
    db.commit()
    db.refresh(connection)
    return me.id


def _ensure_valid_access_token(db: Session, connection: UserIntegrationConnection) -> str:
    encrypted_access = connection.access_token_encrypted
    if not encrypted_access:
        raise ValueError("Missing stored X access token")

    now = _now_naive_utc()
    expires_at = connection.token_expires_at
    if not expires_at or expires_at > now + timedelta(seconds=TOKEN_EXPIRY_SKEW_SECONDS):
        return decrypt_token(encrypted_access)

    encrypted_refresh = connection.refresh_token_encrypted
    if not encrypted_refresh:
        raise ValueError("X access token expired and no refresh token is available")

    refresh_token = decrypt_token(encrypted_refresh)
    refreshed = refresh_oauth_token(refresh_token=refresh_token)
    connection.access_token_encrypted = encrypt_token(refreshed.access_token)
    if refreshed.refresh_token:
        connection.refresh_token_encrypted = encrypt_token(refreshed.refresh_token)
    connection.token_expires_at = _expires_at_from_seconds(refreshed.expires_in)
    if refreshed.scopes:
        connection.scopes = refreshed.scopes
    db.commit()
    db.refresh(connection)
    return refreshed.access_token


def _build_pkce_code_challenge(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")


def _pending_state_expired(created_at: Any) -> bool:
    if not isinstance(created_at, str):
        return True
    try:
        parsed = datetime.fromisoformat(created_at)
    except ValueError:
        return True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    age_seconds = (datetime.now(UTC) - parsed.astimezone(UTC)).total_seconds()
    return age_seconds > OAUTH_PENDING_TTL_MINUTES * 60


def _get_connection(db: Session, *, user_id: int) -> UserIntegrationConnection | None:
    return (
        db.query(UserIntegrationConnection)
        .filter(UserIntegrationConnection.user_id == user_id)
        .filter(UserIntegrationConnection.provider == X_PROVIDER)
        .first()
    )


def _get_or_create_connection(db: Session, *, user_id: int) -> UserIntegrationConnection:
    connection = _get_connection(db, user_id=user_id)
    if connection:
        return connection

    connection = UserIntegrationConnection(
        user_id=user_id,
        provider=X_PROVIDER,
        scopes=list(X_DEFAULT_SCOPES),
        is_active=False,
        connection_metadata={},
    )
    db.add(connection)
    db.flush()
    return connection


def _get_sync_state(
    db: Session,
    *,
    connection_id: int,
) -> UserIntegrationSyncState | None:
    return (
        db.query(UserIntegrationSyncState)
        .filter(UserIntegrationSyncState.connection_id == connection_id)
        .first()
    )


def _get_or_create_sync_state(
    db: Session,
    *,
    connection_id: int,
) -> UserIntegrationSyncState:
    sync_state = _get_sync_state(db, connection_id=connection_id)
    if sync_state:
        return sync_state
    sync_state = UserIntegrationSyncState(
        connection_id=connection_id,
        last_status="never_synced",
        sync_metadata={},
    )
    db.add(sync_state)
    db.flush()
    return sync_state


def _normalize_scopes(scopes: Any) -> list[str]:
    if isinstance(scopes, list):
        return [value.strip() for value in scopes if isinstance(value, str) and value.strip()]
    return []


def _expires_at_from_seconds(expires_in: int | None) -> datetime | None:
    if not expires_in or expires_in <= 0:
        return None
    skewed = max(expires_in - TOKEN_EXPIRY_SKEW_SECONDS, 0)
    return _now_naive_utc() + timedelta(seconds=skewed)


def _now_naive_utc() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _now_utc_iso() -> str:
    return datetime.now(UTC).isoformat()
