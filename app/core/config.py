from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://taskqueue:taskqueue@localhost:5432/taskqueue"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Application
    environment: str = "development"
    debug: bool = True

    # Worker settings
    max_concurrent_jobs: int = 10
    max_cpu_units: int = 8
    max_memory_mb: int = 4096

    # Job settings
    default_job_timeout: int = 3600  # 1 hour
    max_retry_attempts: int = 3
    retry_backoff_multiplier: float = 2.0

    # Logging
    log_level: str = "INFO"

    class Config:
        env_file = ".env"


settings = Settings()
