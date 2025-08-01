"""Configuration settings for ReAgent Sydney."""

from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()


class DatabaseSettings(BaseSettings):
    """Database configuration."""
    
    url: str = Field(default="postgresql+asyncpg://reagent:password@localhost:5432/reagent")
    # Optimized for 50+ concurrent users
    pool_size: int = Field(default=20)  # Increased from 5
    max_overflow: int = Field(default=30)  # Increased from 10
    pool_timeout: int = Field(default=30)
    pool_recycle: int = Field(default=3600)  # 1 hour
    pool_pre_ping: bool = Field(default=True)
    echo: bool = Field(default=False)
    
    # Read replica configurations for load balancing
    read_replicas: List[str] = Field(default=[])
    analytics_replica_url: Optional[str] = Field(default=None)
    
    # Query optimization settings
    statement_timeout: int = Field(default=300)  # 5 minutes
    lock_timeout: int = Field(default=30)  # 30 seconds


class RedisSettings(BaseSettings):
    """Redis configuration."""
    
    url: str = Field(default="redis://localhost:6379/0")
    # Optimized for 50+ concurrent users
    max_connections: int = Field(default=50)  # Increased from 10
    retry_on_timeout: bool = Field(default=True)
    ttl: int = Field(default=3600)  # Default TTL in seconds
    
    # Connection pool settings
    socket_connect_timeout: int = Field(default=5)
    socket_timeout: int = Field(default=5)
    health_check_interval: int = Field(default=30)
    
    # Memory optimization
    max_memory_policy: str = Field(default="allkeys-lru")
    max_memory: str = Field(default="512mb")


class WeaviateSettings(BaseSettings):
    """Weaviate vector database configuration."""
    
    url: str = Field(default="http://localhost:8080")
    api_key: Optional[str] = Field(default=None)
    timeout: int = Field(default=30)
    
    # Performance optimization settings
    query_defaults_limit: int = Field(default=50)
    query_maximum_results: int = Field(default=10000)
    batch_size: int = Field(default=100)
    
    # Connection pool settings
    max_connections: int = Field(default=20)
    connection_timeout: int = Field(default=15)


class APISettings(BaseSettings):
    """External API configuration."""
    
    domain_api_key: Optional[str] = Field(default=None)
    rea_api_key: Optional[str] = Field(default=None)
    corelogic_api_key: Optional[str] = Field(default=None)
    corelogic_secret: Optional[str] = Field(default=None)
    corelogic_base_url: str = Field(default="https://api.corelogic.asia")
    nsw_lpi_api_key: Optional[str] = Field(default=None)
    openai_api_key: Optional[str] = Field(default=None)
    
    # Rate limiting
    domain_rate_limit: int = Field(default=1000)  # calls per day
    rea_rate_limit: int = Field(default=500)      # calls per day
    corelogic_rate_limit: int = Field(default=2000)  # calls per day


class CrewAISettings(BaseSettings):
    """CrewAI configuration."""
    
    # Optimized for concurrent agent execution
    max_workers: int = Field(default=8)  # Increased from 4
    task_timeout: int = Field(default=300)  # 5 minutes
    retry_attempts: int = Field(default=3)
    enable_logging: bool = Field(default=True)
    
    # Resource management
    memory_limit_mb: int = Field(default=2048)
    cpu_limit: float = Field(default=1.5)
    queue_maxsize: int = Field(default=100)


class Settings(BaseSettings):
    """Main application settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_nested_delimiter="__",
        extra="ignore"  # Allow extra fields in .env file
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
    cache: RedisSettings = Field(default_factory=RedisSettings)  # Alias for redis
    weaviate: WeaviateSettings = Field(default_factory=WeaviateSettings)
    apis: APISettings = Field(default_factory=APISettings)
    crewai: CrewAISettings = Field(default_factory=CrewAISettings)


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get global settings instance."""
    return settings