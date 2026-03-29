"""Tests for admin config and output helpers."""

from __future__ import annotations

import argparse
from io import StringIO

from admin.config import resolve_config
from admin.output import Envelope, EnvelopeError, emit


def _namespace(**overrides: object) -> argparse.Namespace:
    defaults = {
        "env_file": None,
        "remote": None,
        "app_dir": None,
        "logs_dir": None,
        "service_log_dir": None,
        "remote_db_path": None,
        "remote_python": None,
        "local_logs_dir": None,
        "local_db_path": None,
        "prompt_report_output_dir": None,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_resolve_config_loads_admin_env_file(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "ADMIN_REMOTE=ops@example.com",
                "ADMIN_APP_DIR=/srv/news_app",
                "ADMIN_LOGS_DIR=/srv/logs",
                "ADMIN_SERVICE_LOG_DIR=/srv/service-logs",
                "ADMIN_REMOTE_DB_PATH=/srv/news.db",
                "ADMIN_REMOTE_PYTHON=/venv/bin/python",
            ]
        )
    )

    config = resolve_config(_namespace(env_file=str(env_file)))

    assert config.remote == "ops@example.com"
    assert config.app_dir == "/srv/news_app"
    assert config.logs_dir == "/srv/logs"
    assert config.service_log_dir == "/srv/service-logs"
    assert config.remote_db_path == "/srv/news.db"
    assert config.remote_python == "/venv/bin/python"


def test_resolve_config_prefers_flags_over_env(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("ADMIN_REMOTE=ops@example.com\n")

    config = resolve_config(_namespace(env_file=str(env_file), remote="override@example.com"))

    assert config.remote == "override@example.com"


def test_emit_json_envelope():
    stream = StringIO()
    emit(Envelope(ok=True, command="db.tables", data={"tables": ["users"]}), "json", stream)

    rendered = stream.getvalue()
    assert '"command": "db.tables"' in rendered
    assert '"tables": [' in rendered


def test_emit_text_error_envelope():
    stream = StringIO()
    emit(
        Envelope(
            ok=False,
            command="db.query",
            error=EnvelopeError("bad query", details={"sql": "delete from users"}),
        ),
        "text",
        stream,
    )

    rendered = stream.getvalue()
    assert "error: bad query" in rendered
    assert '"sql": "delete from users"' in rendered
