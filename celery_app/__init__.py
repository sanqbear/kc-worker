"""
Celery application package for Knowledge Center AI Worker.

This package provides asynchronous task processing for AI operations including:
- Text summarization
- Keyword extraction
- JSON normalization from natural language

Design principles:
- Idempotent task design for safe retries
- Graceful error handling with exponential backoff
- Structured logging with correlation IDs
- Health monitoring and observability
"""

from .celery import app as celery_app

__all__ = ["celery_app"]
