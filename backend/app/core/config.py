from enum import StrEnum
from functools import lru_cache

from pydantic import AnyHttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnvironment(StrEnum):
    LOCAL = "local"
    TEST = "test"
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class SpeechProvider(StrEnum):
    MOCK = "mock"
    LOCAL = "local"
    OPENAI = "openai"
    TWILIO = "twilio"


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Settings(BaseSettings):
    APP_ENV: AppEnvironment = AppEnvironment.LOCAL
    APP_NAME: str = "Voice Agent SaaS"
    API_V1_PREFIX: str = "/api/v1"
    LOG_LEVEL: LogLevel = LogLevel.INFO
    DATABASE_URL: str = "sqlite:///./local.db"
    REDIS_URL: str = "redis://localhost:6379/0"
    SECRET_KEY: str = "change-me"
    PUBLIC_BASE_URL: AnyHttpUrl = AnyHttpUrl("http://localhost:8000")
    DEFAULT_TENANT_ID: str = "demo"
    HUMAN_HANDOFF_FALLBACK_NUMBER: str | None = None
    OPENAI_API_KEY: SecretStr | None = None
    GROQ_API_KEY: SecretStr | None = None
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_FAST_MODEL: str = "llama-3.1-8b-instant"
    # "huggingface" uses a local sentence-transformers model (no API key needed).
    # "fake" forces the deterministic stub — used in tests and CI.
    EMBEDDING_PROVIDER: str = "huggingface"
    EMBEDDING_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    TWILIO_AUTH_TOKEN: SecretStr | None = None
    STT_PROVIDER: SpeechProvider = SpeechProvider.MOCK
    TTS_PROVIDER: SpeechProvider = SpeechProvider.MOCK
    DEFAULT_LANGUAGE: str = "bn-BD"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
