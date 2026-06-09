from pathlib import Path

from pydantic import SecretStr
from pytest import MonkeyPatch

from app.core.config import AppEnvironment, LogLevel, Settings, SpeechProvider

BACKEND_ROOT = Path(__file__).resolve().parents[2]
SETTING_ENV_VARS = (
    "APP_ENV",
    "APP_NAME",
    "API_V1_PREFIX",
    "LOG_LEVEL",
    "DATABASE_URL",
    "REDIS_URL",
    "SECRET_KEY",
    "PUBLIC_BASE_URL",
    "DEFAULT_TENANT_ID",
    "HUMAN_HANDOFF_FALLBACK_NUMBER",
    "OPENAI_API_KEY",
    "TWILIO_AUTH_TOKEN",
    "STT_PROVIDER",
    "TTS_PROVIDER",
    "DEFAULT_LANGUAGE",
)


def clear_settings_environment(monkeypatch: MonkeyPatch) -> None:
    for variable_name in SETTING_ENV_VARS:
        monkeypatch.delenv(variable_name, raising=False)


def test_settings_defaults_support_local_mock_mode(monkeypatch: MonkeyPatch) -> None:
    clear_settings_environment(monkeypatch)
    settings = Settings(_env_file=None)

    assert settings.APP_ENV is AppEnvironment.LOCAL
    assert settings.LOG_LEVEL is LogLevel.INFO
    assert settings.DATABASE_URL == "sqlite:///./local.db"
    assert str(settings.PUBLIC_BASE_URL) == "http://localhost:8000/"
    assert settings.DEFAULT_TENANT_ID == "demo"
    assert settings.HUMAN_HANDOFF_FALLBACK_NUMBER is None
    assert settings.OPENAI_API_KEY is None
    assert settings.TWILIO_AUTH_TOKEN is None
    assert settings.STT_PROVIDER is SpeechProvider.MOCK
    assert settings.TTS_PROVIDER is SpeechProvider.MOCK


def test_env_example_supports_local_startup_without_paid_provider_keys(
    monkeypatch: MonkeyPatch,
) -> None:
    clear_settings_environment(monkeypatch)
    settings = Settings(_env_file=BACKEND_ROOT / ".env.example")

    assert settings.APP_ENV is AppEnvironment.LOCAL
    assert settings.DATABASE_URL == "sqlite:///./local.db"
    assert settings.OPENAI_API_KEY is None
    assert settings.TWILIO_AUTH_TOKEN is None
    assert settings.STT_PROVIDER is SpeechProvider.MOCK
    assert settings.TTS_PROVIDER is SpeechProvider.MOCK


def test_settings_read_typed_environment_values(monkeypatch: MonkeyPatch) -> None:
    clear_settings_environment(monkeypatch)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://voice.example.test")
    monkeypatch.setenv("DEFAULT_TENANT_ID", "tenant-test")
    monkeypatch.setenv("HUMAN_HANDOFF_FALLBACK_NUMBER", "+15555550123")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-value")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "test-twilio-value")
    monkeypatch.setenv("STT_PROVIDER", "local")
    monkeypatch.setenv("TTS_PROVIDER", "mock")

    settings = Settings(_env_file=None)

    assert settings.APP_ENV is AppEnvironment.TEST
    assert settings.LOG_LEVEL is LogLevel.DEBUG
    assert settings.DATABASE_URL == "sqlite:///./test.db"
    assert str(settings.PUBLIC_BASE_URL) == "https://voice.example.test/"
    assert settings.DEFAULT_TENANT_ID == "tenant-test"
    assert settings.HUMAN_HANDOFF_FALLBACK_NUMBER == "+15555550123"
    assert isinstance(settings.OPENAI_API_KEY, SecretStr)
    assert isinstance(settings.TWILIO_AUTH_TOKEN, SecretStr)
    assert settings.STT_PROVIDER is SpeechProvider.LOCAL
    assert settings.TTS_PROVIDER is SpeechProvider.MOCK
