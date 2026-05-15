"""Unit tests for config module."""
from app.core.config import get_settings


def test_settings_load():
    settings = get_settings()
    assert settings.app_name == "coupon-decision-agent"
    assert settings.app_version == "0.1.0"


def test_settings_env_override(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    settings = get_settings()
    assert settings.app_env == "test"
