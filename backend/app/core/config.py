from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_ENV: str = "local"
    APP_NAME: str = "Voice Agent SaaS"
    API_V1_PREFIX: str = "/api/v1"
    DATABASE_URL: str = "sqlite:///./local.db"
    REDIS_URL: str = "redis://localhost:6379/0"
    SECRET_KEY: str = "change-me"
    PUBLIC_BASE_URL: str = "http://localhost:8000"
    DEFAULT_LANGUAGE: str = "bn-BD"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
