"""
Configuration management for the Celery worker service.

Uses Pydantic Settings for environment-based configuration with validation.
All sensitive values (Redis URL, API keys) should be provided via environment variables.
"""

import os
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Configuration priority:
    1. Environment variables
    2. .env file
    3. Default values
    """

    # Redis configuration
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for Celery broker and result backend"
    )

    # LLM Server configuration
    llm_server_url: str = Field(
        default="http://localhost:8000",
        description="Base URL for the LLM inference server"
    )

    llm_backend: Literal["llamacpp", "vllm"] = Field(
        default="llamacpp",
        description="LLM backend type (llamacpp or vllm)"
    )

    llm_model: str = Field(
        default="",
        description="Model name or path (backend-specific)"
    )

    # LLM generation parameters
    max_tokens: int = Field(
        default=1024,
        ge=1,
        le=32000,
        description="Maximum tokens to generate"
    )

    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature for generation"
    )

    top_p: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
        description="Nucleus sampling parameter"
    )

    top_k: int = Field(
        default=40,
        ge=1,
        description="Top-k sampling parameter"
    )

    # Task timeout and retry configuration
    task_soft_time_limit: int = Field(
        default=180,
        ge=1,
        description="Soft time limit for tasks in seconds (raises exception)"
    )

    task_time_limit: int = Field(
        default=300,
        ge=1,
        description="Hard time limit for tasks in seconds (kills task)"
    )

    task_max_retries: int = Field(
        default=3,
        ge=0,
        description="Maximum number of retries for failed tasks"
    )

    task_retry_delay: int = Field(
        default=60,
        ge=1,
        description="Initial retry delay in seconds (uses exponential backoff)"
    )

    # Logging configuration
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level"
    )

    log_format: Literal["json", "text"] = Field(
        default="json",
        description="Log output format (json for production, text for development)"
    )

    # Worker configuration
    worker_concurrency: int = Field(
        default=4,
        ge=1,
        description="Number of concurrent worker processes"
    )

    worker_prefetch_multiplier: int = Field(
        default=1,
        ge=1,
        description="Number of tasks to prefetch per worker (1 = fair scheduling)"
    )

    # Environment
    environment: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Deployment environment"
    )

    # Health check configuration
    health_check_enabled: bool = Field(
        default=True,
        description="Enable health check endpoints"
    )

    health_check_port: int = Field(
        default=8001,
        ge=1024,
        le=65535,
        description="Port for health check HTTP server"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    @field_validator("redis_url")
    @classmethod
    def validate_redis_url(cls, v: str) -> str:
        """Validate Redis URL format."""
        if not v.startswith(("redis://", "rediss://")):
            raise ValueError("Redis URL must start with redis:// or rediss://")
        return v

    @field_validator("llm_server_url")
    @classmethod
    def validate_llm_server_url(cls, v: str) -> str:
        """Validate LLM server URL format."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("LLM server URL must start with http:// or https://")
        return v.rstrip("/")

    @field_validator("task_time_limit")
    @classmethod
    def validate_task_time_limit(cls, v: int, info) -> int:
        """Ensure hard time limit is greater than soft time limit."""
        if "task_soft_time_limit" in info.data and v <= info.data["task_soft_time_limit"]:
            raise ValueError("task_time_limit must be greater than task_soft_time_limit")
        return v


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """
    Get the global settings instance.

    This function allows for easier testing by enabling settings injection.

    Returns:
        Settings: The global settings instance
    """
    return settings
