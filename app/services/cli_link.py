"""QR approval sessions for linking the Newsly CLI to a user account."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy.orm import Session

from app.infrastructure.security.key_hashing import hash_api_key, verify_api_key_hash
from app.models.schema import CliLinkSession, UserApiKey
from app.models.user import User
from app.repositories.api_key_repository import create_api_key

CLI_LINK_SESSION_TTL_MINUTES = 10
CliLinkStatus = Literal["pending", "approved", "claimed", "expired"]


@dataclass(frozen=True)
class StartedCliLinkSession:
    """Start response returned to an unauthenticated CLI."""

    session_id: str
    poll_token: str
    approve_url: str
    expires_at: datetime


@dataclass(frozen=True)
class ApprovedCliLinkSession:
    """Approval response returned to the authenticated app."""

    session_id: str
    key_prefix: str
    expires_at: datetime


@dataclass(frozen=True)
class PolledCliLinkSession:
    """Polling snapshot returned to the unauthenticated CLI."""

    session_id: str
    status: CliLinkStatus
    expires_at: datetime
    api_key: str | None = None
    key_prefix: str | None = None


def start_cli_link_session(
    db: Session,
    *,
    device_name: str | None = None,
) -> StartedCliLinkSession:
    """Create a short-lived CLI link session and return polling/bootstrap data."""
    session_id = secrets.token_urlsafe(12)
    approve_token = secrets.token_urlsafe(24)
    poll_token = secrets.token_urlsafe(24)
    expires_at = _utcnow() + timedelta(minutes=CLI_LINK_SESSION_TTL_MINUTES)

    session = CliLinkSession(
        session_id=session_id,
        approve_token_hash=hash_api_key(approve_token),
        poll_token_hash=hash_api_key(poll_token),
        requested_device_name=(device_name or "").strip() or None,
        status="pending",
        expires_at=expires_at.replace(tzinfo=None),
    )
    db.add(session)
    db.commit()

    approve_url = f"newsly://cli-link?session_id={session_id}&approve_token={approve_token}"
    return StartedCliLinkSession(
        session_id=session_id,
        poll_token=poll_token,
        approve_url=approve_url,
        expires_at=expires_at,
    )


def approve_cli_link_session(
    db: Session,
    *,
    session_id: str,
    approve_token: str,
    user: User,
    device_name: str | None = None,
) -> ApprovedCliLinkSession:
    """Approve a pending CLI link session and mint an API key for the user."""
    session = _get_cli_link_session(db, session_id=session_id)
    if session is None:
        raise ValueError("CLI link session not found")
    if _is_expired(session):
        session.status = "expired"
        db.commit()
        raise ValueError("CLI link session expired")
    if not verify_api_key_hash(approve_token, session.approve_token_hash):
        raise ValueError("Invalid CLI link approval token")

    if session.status == "approved" and session.user_api_key_id is not None:
        record = _get_user_api_key(db, api_key_id=session.user_api_key_id)
        if record is None:
            raise ValueError("CLI link API key missing")
        return ApprovedCliLinkSession(
            session_id=session.session_id,
            key_prefix=record.key_prefix,
            expires_at=_as_utc(session.expires_at),
        )
    if session.status == "claimed":
        raise ValueError("CLI link session already claimed")

    record, raw_key = create_api_key(
        db,
        user_id=user.id,
        created_by_admin_user_id=None,
    )
    session.status = "approved"
    session.approved_by_user_id = user.id
    session.user_api_key_id = int(record.id)
    session.issued_api_key_plaintext = raw_key
    session.requested_device_name = (device_name or "").strip() or session.requested_device_name
    session.approved_at = _utcnow().replace(tzinfo=None)
    db.commit()

    return ApprovedCliLinkSession(
        session_id=session.session_id,
        key_prefix=record.key_prefix,
        expires_at=_as_utc(session.expires_at),
    )


def poll_cli_link_session(
    db: Session,
    *,
    session_id: str,
    poll_token: str,
) -> PolledCliLinkSession:
    """Return current CLI link status, revealing the raw API key once."""
    session = _get_cli_link_session(db, session_id=session_id)
    if session is None:
        raise ValueError("CLI link session not found")
    if not verify_api_key_hash(poll_token, session.poll_token_hash):
        raise ValueError("Invalid CLI link polling token")

    if _is_expired(session) and session.status == "pending":
        session.status = "expired"
        db.commit()

    key_prefix = None
    if session.user_api_key_id is not None:
        record = _get_user_api_key(db, api_key_id=session.user_api_key_id)
        key_prefix = record.key_prefix if record is not None else None

    if session.status == "approved" and session.issued_api_key_plaintext:
        raw_key = session.issued_api_key_plaintext
        session.issued_api_key_plaintext = None
        session.status = "claimed"
        session.claimed_at = _utcnow().replace(tzinfo=None)
        db.commit()
        return PolledCliLinkSession(
            session_id=session.session_id,
            status="approved",
            expires_at=_as_utc(session.expires_at),
            api_key=raw_key,
            key_prefix=key_prefix,
        )

    return PolledCliLinkSession(
        session_id=session.session_id,
        status=_status_for_poll(session),
        expires_at=_as_utc(session.expires_at),
        api_key=None,
        key_prefix=key_prefix,
    )


def _get_cli_link_session(db: Session, *, session_id: str) -> CliLinkSession | None:
    return db.query(CliLinkSession).filter(CliLinkSession.session_id == session_id).first()


def _get_user_api_key(db: Session, *, api_key_id: int) -> UserApiKey | None:
    return db.query(UserApiKey).filter(UserApiKey.id == api_key_id).first()


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _is_expired(session: CliLinkSession) -> bool:
    return _as_utc(session.expires_at) <= _utcnow()


def _status_for_poll(session: CliLinkSession) -> CliLinkStatus:
    if _is_expired(session) and session.status in {"pending", "approved"}:
        return "expired"
    if session.status == "approved":
        return "approved"
    if session.status == "claimed":
        return "claimed"
    return "pending"
