from pathlib import Path


def test_start_workers_script_is_non_interactive_when_queue_empty() -> None:
    """Ensure the worker startup script does not prompt when queue is empty."""
    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / "scripts" / "start_workers.sh"
    script_text = script_path.read_text(encoding="utf-8")

    assert "Do you want to continue anyway?" not in script_text
    assert "Continuing without prompt" in script_text
    assert "Ensuring Playwright Chromium browser is available" in script_text
    assert ".venv/bin/playwright install chromium" in script_text
    assert "playwright install firefox" not in script_text
    assert "playwright install webkit" not in script_text
    assert "playwright install-deps" not in script_text


def test_push_app_script_finalizes_uv_environment() -> None:
    """Ensure deploy script enforces pipx-based uv env bootstrap."""
    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / "scripts" / "deploy" / "push_app.sh"
    script_text = script_path.read_text(encoding="utf-8")
    setup_script_path = repo_root / "scripts" / "setup_uv_env.sh"
    setup_script_text = setup_script_path.read_text(encoding="utf-8")

    assert "pipx install uv --force" in setup_script_text
    assert "uv python install \"$PYTHON_VERSION\"" in setup_script_text
    assert "uv venv --python \"$PYTHON_VERSION\" .venv" in setup_script_text
    assert 'SYNC_ARGS+=(--frozen)' in setup_script_text
    assert "sudo -n sha256sum" in script_text
    assert "SHOULD_REMOVE_REMOTE_VENV" in script_text
    assert "uv.lock changed; removing remote virtualenv" in script_text
    assert "uv.lock unchanged; preserving remote virtualenv" in script_text
