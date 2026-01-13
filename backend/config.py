"""Centralized configuration loaded from environment variables."""
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    app_host: str = Field("0.0.0.0", alias="APP_HOST")
    app_port: int = Field(8000, alias="APP_PORT")
    database_url: str = Field("sqlite:///./data/outreach.db", alias="DATABASE_URL")
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    dry_run: bool = Field(True, alias="DRY_RUN")
    ai_mode: bool = Field(False, alias="AI_MODE")
    rate_limit_per_minute: int = Field(10, alias="RATE_LIMIT_PER_MINUTE")
    max_retries: int = Field(2, alias="MAX_RETRIES")

    groq_api_key: str | None = Field(None, alias="GROQ_API_KEY")
    groq_model: str = Field("llama-3.1-70b-versatile", alias="GROQ_MODEL")

    smtp_host: str = Field("localhost", alias="SMTP_HOST")
    smtp_port: int = Field(1025, alias="SMTP_PORT")
    smtp_username: str | None = Field(None, alias="SMTP_USERNAME")
    smtp_password: str | None = Field(None, alias="SMTP_PASSWORD")
    smtp_use_tls: bool = Field(False, alias="SMTP_USE_TLS")

    openai_api_key: str | None = Field(None, alias="OPENAI_API_KEY")
    llm_model: str = Field("gpt-4o-mini", alias="LLM_MODEL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def get_settings() -> Settings:
    return Settings()  # type: ignore[arg-type]
