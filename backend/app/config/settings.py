"""
Application Configuration Module

Uses pydantic-settings for type-safe environment variable handling.
Following official Pydantic Settings documentation:
https://docs.pydantic.dev/latest/concepts/pydantic_settings/
"""

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    All settings are automatically loaded from:
    1. Environment variables
    2. .env file (if present)
    
    Environment variables take precedence over .env file values.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # =========================================================================
    # Application Settings
    # =========================================================================
    app_name: str = Field(default="News Intelligence System", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=False, alias="DEBUG")
    
    # Secret keys
    secret_key: str = Field(..., alias="SECRET_KEY")
    jwt_secret_key: str = Field(..., alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_access_token_expire_minutes: int = Field(
        default=10080,  # 7 days
        alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES"
    )
    
    # =========================================================================
    # Database Settings
    # =========================================================================
    database_url: str = Field(..., alias="DATABASE_URL")
    
    # Individual DB settings (for fallback URL construction)
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_user: str = Field(default="newsapp", alias="POSTGRES_USER")
    postgres_password: str = Field(default="", alias="POSTGRES_PASSWORD")
    postgres_db: str = Field(default="news_intelligence", alias="POSTGRES_DB")
    
    # =========================================================================
    # Redis Settings
    # =========================================================================
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    
    # =========================================================================
    # Celery Settings
    # =========================================================================
    celery_broker_url: str = Field(
        default="redis://localhost:6379/0",
        alias="CELERY_BROKER_URL"
    )
    celery_result_backend: str = Field(
        default="redis://localhost:6379/0",
        alias="CELERY_RESULT_BACKEND"
    )
    
    # =========================================================================
    # CORS Settings
    # =========================================================================
    frontend_url: str = Field(
        default="http://localhost:5173",
        alias="FRONTEND_URL"
    )
    allowed_origins: str = Field(
        default="http://localhost:5173,http://localhost:3000,https://newsiq-frontend.onrender.com",
        alias="ALLOWED_ORIGINS"
    )
    
    @property
    def cors_origins(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        origins = [origin.strip() for origin in self.allowed_origins.split(",")]
        # Also add frontend_url if not already in list
        if self.frontend_url and self.frontend_url not in origins:
            origins.append(self.frontend_url)
        return origins
    
    # =========================================================================
    # API Keys
    # =========================================================================
    google_api_key: str = Field(..., alias="GOOGLE_API_KEY")
    
    # =========================================================================
    # Embedding Settings
    # =========================================================================
    embedding_model: str = Field(
        default="models/text-embedding-004",
        alias="EMBEDDING_MODEL"
    )
    embedding_dimensions: int = Field(default=768, alias="EMBEDDING_DIMENSIONS")
    embedding_batch_size: int = Field(default=100, alias="EMBEDDING_BATCH_SIZE")
    
    # =========================================================================
    # LLM Settings (Gemini)
    # =========================================================================
    gemini_model: str = Field(
        default="gemini-2.5-flash",
        alias="GEMINI_MODEL"
    )
    gemini_max_tokens: int = Field(default=1024, alias="GEMINI_MAX_TOKENS")
    deep_research_cache_ttl_hours: int = Field(
        default=24,
        alias="DEEP_RESEARCH_CACHE_TTL_HOURS"
    )
    
    # =========================================================================
    # Content Extraction Settings
    # =========================================================================
    rss_fetch_interval_minutes: int = Field(
        default=5,
        alias="RSS_FETCH_INTERVAL_MINUTES"
    )
    max_articles_per_fetch: int = Field(default=50, alias="MAX_ARTICLES_PER_FETCH")
    content_extraction_timeout: int = Field(
        default=30,
        alias="CONTENT_EXTRACTION_TIMEOUT"
    )
    
    # =========================================================================
    # Rate Limiting
    # =========================================================================
    rate_limit_per_minute: int = Field(default=100, alias="RATE_LIMIT_PER_MINUTE")
    deep_research_rate_limit_per_minute: int = Field(
        default=5,
        alias="DEEP_RESEARCH_RATE_LIMIT_PER_MINUTE"
    )
    
    # =========================================================================
    # Personalization Settings
    # =========================================================================
    long_term_weight: float = Field(default=0.7, alias="LONG_TERM_WEIGHT")
    session_weight: float = Field(default=0.3, alias="SESSION_WEIGHT")
    diversity_percentage: int = Field(default=25, alias="DIVERSITY_PERCENTAGE")
    blind_spot_percentage: int = Field(default=5, alias="BLIND_SPOT_PERCENTAGE")
    
    @field_validator("long_term_weight", "session_weight")
    @classmethod
    def validate_weights(cls, v: float) -> float:
        """Ensure weights are between 0 and 1."""
        if not 0 <= v <= 1:
            raise ValueError("Weight must be between 0 and 1")
        return v


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Uses lru_cache to ensure settings are only loaded once.
    This follows the FastAPI best practice for configuration.
    """
    return Settings()


# Export settings instance for convenience
settings = get_settings()
