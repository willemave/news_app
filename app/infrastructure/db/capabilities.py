"""Small database capability helpers."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class DatabaseCapabilities:
    """Capabilities exposed to repositories/application code."""

    full_text_search: bool
    native_json_ops: bool


def get_database_capabilities(db: Session) -> DatabaseCapabilities:
    """Infer DB capabilities from the active SQLAlchemy bind."""
    bind = db.get_bind()
    dialect = bind.dialect.name
    return DatabaseCapabilities(
        full_text_search=dialect == "sqlite",
        native_json_ops=dialect != "sqlite",
    )
