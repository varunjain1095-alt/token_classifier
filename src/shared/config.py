"""Configuration loading for the application."""
import os
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # OpenAI Configuration; optional at boot so the container starts;
    # preview/classification surfaces its own error when no key is set.
    openai_api_key: str = Field("", env="OPENAI_API_KEY")
    openai_model_name: str = Field("gpt-5-mini", env="OPENAI_MODEL_NAME")

    # Database Configuration; optional; the app falls back to in-memory/
    # filesystem storage when no database is configured.
    database_url: str = Field("", env="DATABASE_URL")
    postgres_host: str = Field("localhost", env="POSTGRES_HOST")
    postgres_port: int = Field(5432, env="POSTGRES_PORT")
    postgres_db: str = Field("review_classification", env="POSTGRES_DB")
    postgres_user: str = Field("postgres", env="POSTGRES_USER")
    postgres_password: str = Field("", env="POSTGRES_PASSWORD")
    
    # Redis Configuration
    redis_url: str = Field("redis://localhost:6379/0", env="REDIS_URL")
    celery_broker_url: str = Field("redis://localhost:6379/1", env="CELERY_BROKER_URL")
    celery_result_backend: str = Field("redis://localhost:6379/2", env="CELERY_RESULT_BACKEND")
    
    # Application Configuration
    secret_key: str = Field("change-me-in-production", env="SECRET_KEY")
    flask_env: str = Field("development", env="FLASK_ENV")
    debug: bool = Field(True, env="DEBUG")
    
    # File Storage
    upload_folder: str = Field("./tmp/uploads", env="UPLOAD_FOLDER")
    max_upload_size: int = Field(52428800, env="MAX_UPLOAD_SIZE")  # 50 MB
    
    # Retention Policies (in seconds)
    anonymous_data_retention: int = Field(86400, env="ANONYMOUS_DATA_RETENTION")  # 24 hours
    signed_in_project_retention: int = Field(604800, env="SIGNED_IN_PROJECT_RETENTION")  # 7 days
    
    # Rate Limits
    free_preview_limit: int = Field(1, env="FREE_PREVIEW_LIMIT")
    rate_limit_requests_per_minute: int = Field(60, env="RATE_LIMIT_REQUESTS_PER_MINUTE")
    
    # Session Configuration
    session_timeout: int = Field(3600, env="SESSION_TIMEOUT")  # 1 hour
    permanent_session_lifetime: int = Field(86400, env="PERMANENT_SESSION_LIFETIME")  # 24 hours
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
