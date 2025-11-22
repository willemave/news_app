"""Date parsing utilities with timezone normalization."""

from __future__ import annotations

from datetime import UTC, datetime, tzinfo
from typing import Mapping

from dateutil import parser as date_parser
from dateutil import tz

TZ_ALIASES: Mapping[str, tzinfo | None] = {
    "EST": tz.gettz("America/New_York"),
    "EDT": tz.gettz("America/New_York"),
    "CST": tz.gettz("America/Chicago"),
    "CDT": tz.gettz("America/Chicago"),
    "MST": tz.gettz("America/Denver"),
    "MDT": tz.gettz("America/Denver"),
    "PST": tz.gettz("America/Los_Angeles"),
    "PDT": tz.gettz("America/Los_Angeles"),
    "UTC": UTC,
    "GMT": UTC,
}


def parse_date_with_tz(value: str | datetime | None, default_tz: tzinfo = UTC) -> datetime | None:
    """Parse a date value and return a timezone-aware UTC datetime.

    Args:
        value: Date string or datetime instance to parse.
        default_tz: Applied when the parsed datetime is naive.

    Returns:
        A timezone-aware datetime normalized to UTC, or None if parsing fails.
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = date_parser.parse(value, tzinfos=TZ_ALIASES)
        except (ValueError, TypeError, date_parser.ParserError):
            return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=default_tz)
    else:
        parsed = parsed.astimezone(UTC)

    return parsed
