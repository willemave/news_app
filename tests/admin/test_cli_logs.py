"""Tests for log-related admin CLI behavior."""

from __future__ import annotations

from pathlib import Path

from admin.cli import _handle_logs, build_parser
from admin.config import AdminConfig


def _config(tmp_path: Path) -> AdminConfig:
    return AdminConfig(
        env_file=tmp_path / ".env",
        remote="willem@host",
        app_dir="/opt/news_app",
        docker_service_name="newsly",
        logs_dir="/data/logs",
        service_log_dir="/var/log/news_app",
        remote_db_path="/data/news_app.db",
        remote_python=".venv/bin/python",
        remote_context_source="app-settings",
        local_logs_dir=tmp_path / "logs",
        local_db_path=tmp_path / "news_app.db",
        prompt_report_output_dir=tmp_path / "outputs",
    )


def test_logs_tail_uses_docker_compose_logs(monkeypatch, tmp_path):
    args = build_parser().parse_args(["logs", "tail", "--limit", "12"])
    captured: dict[str, object] = {}

    def fake_run_remote_docker_logs(config, *, tail):
        captured["config"] = config
        captured["tail"] = tail
        return {"source": "docker", "stdout": "line 1\nline 2\n"}

    monkeypatch.setattr("admin.cli.run_remote_docker_logs", fake_run_remote_docker_logs)

    result = _handle_logs(args, config=_config(tmp_path))

    assert result.data["stdout"] == "line 1\nline 2\n"
    assert captured["tail"] == 12
    assert captured["config"].docker_service_name == "newsly"
    assert args.source == "docker"
