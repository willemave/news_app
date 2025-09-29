from pathlib import Path

import pytest

from app.utils.paths import PROJECT_ROOT, resolve_config_path


def test_resolve_config_path_absolute(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_file = tmp_path / "custom.yml"
    config_file.write_text("subreddits: []", encoding="utf-8")

    monkeypatch.setenv("REDDIT_CONFIG_PATH", str(config_file))

    resolved = resolve_config_path("REDDIT_CONFIG_PATH", "config/reddit.yml")

    assert resolved == config_file


def test_resolve_config_path_relative_cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    rel_path = Path("configs/reddit.yml")
    rel_path.parent.mkdir(parents=True, exist_ok=True)
    rel_path.write_text("subreddits: []", encoding="utf-8")

    monkeypatch.setenv("REDDIT_CONFIG_PATH", str(rel_path))

    resolved = resolve_config_path("REDDIT_CONFIG_PATH", "config/reddit.yml")

    assert resolved == rel_path.resolve()


def test_resolve_config_path_default_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REDDIT_CONFIG_PATH", raising=False)

    resolved = resolve_config_path("REDDIT_CONFIG_PATH", "config/reddit.yml")

    assert resolved == (PROJECT_ROOT / "config" / "reddit.yml").resolve()
