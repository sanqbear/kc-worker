"""
Main entry point for the Celery worker with health check server.

This module starts both the Celery worker and the health check HTTP server.
"""

import asyncio
import sys
import threading
from typing import NoReturn

from .celery import app
from .config import settings
from .health import run_health_server
from .utils.logging import get_logger


logger = get_logger(__name__)


def start_health_server_thread() -> threading.Thread:
    """
    Start the health check server in a background thread.

    Returns:
        threading.Thread: The health server thread
    """
    health_thread = threading.Thread(
        target=run_health_server,
        name="HealthServer",
        daemon=True
    )
    health_thread.start()
    logger.info("Health server thread started")
    return health_thread


def main() -> NoReturn:
    """
    Main entry point for the worker process.

    Starts:
    1. Health check HTTP server (in background thread)
    2. Celery worker (in main thread)
    """
    logger.info(
        "Starting Celery worker",
        extra={
            "environment": settings.environment,
            "redis_url": settings.redis_url,
            "llm_backend": settings.llm_backend,
            "concurrency": settings.worker_concurrency,
        }
    )

    # Start health check server in background thread
    if settings.health_check_enabled:
        health_thread = start_health_server_thread()

    # Start Celery worker (blocking)
    # This is equivalent to: celery -A celery_app.celery worker
    try:
        app.worker_main(argv=[
            "worker",
            f"--loglevel={settings.log_level.lower()}",
            f"--concurrency={settings.worker_concurrency}",
            "--max-tasks-per-child=1000",  # Restart worker after 1000 tasks
            "--task-events",  # Enable task events for monitoring
            "--without-gossip",  # Disable gossip for better performance
            "--without-mingle",  # Disable mingle for faster startup
        ])
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
        sys.exit(0)


if __name__ == "__main__":
    main()
