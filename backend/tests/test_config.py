"""Phase 1 gate: configuration loads from environment, no hardcoded secrets."""
import os

from app.core.config import Settings


def test_settings_have_sane_defaults():
    s = Settings()
    assert s.app_version
    assert s.backend_port == 8000
    assert "postgresql" in s.database_url or "sqlite" in s.database_url


def test_no_hardcoded_secrets_in_defaults():
    s = Settings()
    # Defaults must not contain real-looking credentials.
    for value in (s.database_url, s.frontend_url):
        assert "sk-" not in value
        assert "api_key" not in value.lower()


def test_env_overrides_config(monkeypatch):
    monkeypatch.setenv("APP_VERSION", "9.9.9-test")
    s = Settings()
    assert s.app_version == "9.9.9-test"
    # os import used to keep linters honest about env handling
    assert os.environ["APP_VERSION"] == "9.9.9-test"
