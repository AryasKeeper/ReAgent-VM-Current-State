"""Configuration settings for ReAgent Sydney."""

from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database configuration."""
    
    url: str = Field(default="postgresql+asyncpg://reagent:password@localhost:5432/reagent")
    pool_size: int = Field(default=5)
    max_overflow: int = Field(default=10)
    pool_timeout: int = Field(default=30)
    echo: bool = Field(default=False)


class RedisSettings(BaseSettings):
    """Redis configuration."""
    
    url: str = Field(default="redis://localhost:6379/0")
    max_connections: int = Field(default=10)
    retry_on_timeout: bool = Field(default=True)


class WeaviateSettings(BaseSettings):
    """Weaviate vector database configuration."""
    
    url: str = Field(default="http://localhost:8080")
    api_key: Optional[str] = Field(default=None)
    timeout: int = Field(default=30)


class APISettings(BaseSettings):
    """External API configuration."""
    
    domain_api_key: Optional[str] = Field(default=None)
    rea_api_key: Optional[str] = Field(default=None)
    corelogic_api_key: Optional[str] = Field(default=None)
    nsw_lpi_api_key: Optional[str] = Field(default=None)
    openai_api_key: Optional[str] = Field(default=None)
    
    # Rate limiting
    domain_rate_limit: int = Field(default=1000)  # calls per day
    rea_rate_limit: int = Field(default=500)      # calls per day


class CrewAISettings(BaseSettings):
    """CrewAI configuration."""
    
    max_workers: int = Field(default=4)
    task_timeout: int = Field(default=300)  # 5 minutes
    retry_attempts: int = Field(default=3)
    enable_logging: bool = Field(default=True)


class Settings(BaseSettings):
    """Main application settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_nested_delimiter="__"
    )
    
    # App metadata
    app_name: str = Field(default="ReAgent Sydney")
    version: str = Field(default="0.1.0")
    debug: bool = Field(default=False)
    environment: str = Field(default="development")
    
    # API configuration
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    api_workers: int = Field(default=1)
    
    # Security
    secret_key: str = Field(default="your-secret-key-change-in-production")
    allowed_hosts: List[str] = Field(default=["*"])
    cors_origins: List[str] = Field(default=["http://localhost:3000"])
    
    # Logging
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")
    
    # External services
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    weaviate: WeaviateSettings = Field(default_factory=WeaviateSettings)
    apis: APISettings = Field(default_factory=APISettings)
    crewai: CrewAISettings = Field(default_factory=CrewAISettings)


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get global settings instance."""
    return settings