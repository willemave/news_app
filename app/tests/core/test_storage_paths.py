from app.core.settings import Settings, get_settings
from app.utils.error_logger import create_error_logger


def test_settings_default_directories(monkeypatch, tmp_path):
    """Ensure default directory configuration respects the current working directory."""

    monkeypatch.chdir(tmp_path)
    settings = Settings(
        database_url="sqlite:///tmp.db",
        JWT_SECRET_KEY="test-secret-key",
        ADMIN_PASSWORD="test-admin-password"
    )

    assert settings.media_base_dir == tmp_path / "data" / "media"
    assert settings.logs_base_dir == tmp_path / "logs"
    assert settings.podcast_media_dir == (tmp_path / "data" / "media" / "podcasts").resolve()
    assert settings.logs_dir == (tmp_path / "logs").resolve()


def test_error_logger_respects_configured_logs_dir(monkeypatch, tmp_path):
    """Ensure the error logger writes files to the configured logs directory."""

    log_root = tmp_path / "custom_logs"
    monkeypatch.setenv("DATABASE_URL", "sqlite:///tmp.db")
    monkeypatch.setenv("LOGS_BASE_DIR", str(log_root))
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("ADMIN_PASSWORD", "test-admin-password")

    get_settings.cache_clear()
    try:
        logger = create_error_logger("test_component")
        expected_dir = (log_root / "errors").resolve()

        assert logger.log_dir == expected_dir
        assert logger.log_dir.exists()
        assert logger.log_file.parent == expected_dir
    finally:
        get_settings.cache_clear()
