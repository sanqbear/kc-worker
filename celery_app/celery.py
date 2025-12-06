"""
Celery application initialization and configuration.

This module sets up the Celery application with:
- Redis as both broker and result backend
- JSON serialization for cross-language compatibility
- Task routing and execution policies
- Graceful shutdown handling
- Dead letter queue configuration
"""

import signal
import sys
from typing import Any, Dict

from celery import Celery, signals
from celery.signals import worker_shutting_down, worker_ready
from kombu import Exchange, Queue

from .config import settings
from .utils.logging import setup_logging


# Initialize structured logging
logger = setup_logging()


def create_celery_app() -> Celery:
    """
    Create and configure the Celery application.

    Returns:
        Celery: Configured Celery application instance
    """
    app = Celery(
        "worker",
        broker=settings.redis_url,
        backend=settings.redis_url,
        include=[
            "celery_app.tasks.summarize",
            "celery_app.tasks.keywords",
            "celery_app.tasks.normalize",
        ]
    )

    # Task execution configuration
    app.conf.update(
        # Serialization
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",

        # Timezone
        timezone="UTC",
        enable_utc=True,

        # Task tracking
        task_track_started=True,
        task_send_sent_event=True,

        # Time limits
        task_soft_time_limit=settings.task_soft_time_limit,
        task_time_limit=settings.task_time_limit,

        # Retry configuration
        task_acks_late=True,  # Acknowledge after task completes (ensures retries on failure)
        task_reject_on_worker_lost=True,  # Requeue if worker dies

        # Result backend
        result_expires=3600,  # Results expire after 1 hour
        result_persistent=True,  # Persist results to Redis
        result_extended=True,  # Store additional metadata

        # Worker configuration
        worker_prefetch_multiplier=settings.worker_prefetch_multiplier,
        worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks (prevent memory leaks)
        worker_disable_rate_limits=False,

        # Logging
        worker_hijack_root_logger=False,  # Use our custom logger
        worker_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
        worker_task_log_format="[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s",
    )

    # Configure queues with dead letter exchange
    default_exchange = Exchange("default", type="direct")
    dlx_exchange = Exchange("dlx", type="direct")

    app.conf.task_queues = (
        # Main task queues
        Queue(
            "default",
            exchange=default_exchange,
            routing_key="default",
            queue_arguments={
                "x-dead-letter-exchange": "dlx",
                "x-dead-letter-routing-key": "default.dlq",
            }
        ),
        Queue(
            "summarize",
            exchange=default_exchange,
            routing_key="summarize",
            queue_arguments={
                "x-dead-letter-exchange": "dlx",
                "x-dead-letter-routing-key": "summarize.dlq",
            }
        ),
        Queue(
            "keywords",
            exchange=default_exchange,
            routing_key="keywords",
            queue_arguments={
                "x-dead-letter-exchange": "dlx",
                "x-dead-letter-routing-key": "keywords.dlq",
            }
        ),
        Queue(
            "normalize",
            exchange=default_exchange,
            routing_key="normalize",
            queue_arguments={
                "x-dead-letter-exchange": "dlx",
                "x-dead-letter-routing-key": "normalize.dlq",
            }
        ),
        # Dead letter queues
        Queue("default.dlq", exchange=dlx_exchange, routing_key="default.dlq"),
        Queue("summarize.dlq", exchange=dlx_exchange, routing_key="summarize.dlq"),
        Queue("keywords.dlq", exchange=dlx_exchange, routing_key="keywords.dlq"),
        Queue("normalize.dlq", exchange=dlx_exchange, routing_key="normalize.dlq"),
    )

    # Default queue for unrouted tasks
    app.conf.task_default_queue = "default"
    app.conf.task_default_exchange = "default"
    app.conf.task_default_routing_key = "default"

    # Task routing
    app.conf.task_routes = {
        "celery_app.tasks.summarize.summarize_text": {"queue": "summarize"},
        "celery_app.tasks.keywords.extract_keywords": {"queue": "keywords"},
        "celery_app.tasks.normalize.normalize_json": {"queue": "normalize"},
    }

    return app


# Create the Celery app instance
app = create_celery_app()


@signals.setup_logging.connect
def setup_celery_logging(**kwargs: Any) -> None:
    """
    Configure logging when Celery worker starts.

    This signal handler overrides Celery's default logging setup.
    """
    # Our custom logging is already configured in setup_logging()
    pass


@worker_ready.connect
def on_worker_ready(sender: Any, **kwargs: Any) -> None:
    """
    Called when worker is ready to accept tasks.

    Args:
        sender: The worker instance
        **kwargs: Additional keyword arguments
    """
    logger.info(
        "Worker ready to process tasks",
        extra={
            "environment": settings.environment,
            "concurrency": settings.worker_concurrency,
            "prefetch_multiplier": settings.worker_prefetch_multiplier,
        }
    )


@worker_shutting_down.connect
def on_worker_shutdown(sig: int, how: str, exitcode: int, **kwargs: Any) -> None:
    """
    Called when worker begins graceful shutdown.

    Args:
        sig: Signal number that triggered shutdown
        how: How the worker is shutting down
        exitcode: Exit code
        **kwargs: Additional keyword arguments
    """
    logger.info(
        "Worker shutting down gracefully",
        extra={
            "signal": sig,
            "how": how,
            "exitcode": exitcode,
        }
    )


def handle_shutdown_signal(signum: int, frame: Any) -> None:
    """
    Handle shutdown signals for graceful termination.

    Args:
        signum: Signal number
        frame: Current stack frame
    """
    signal_name = signal.Signals(signum).name
    logger.info(f"Received {signal_name}, initiating graceful shutdown...")

    # Celery will handle the graceful shutdown internally
    # We just need to exit cleanly
    sys.exit(0)


# Register signal handlers for graceful shutdown
signal.signal(signal.SIGTERM, handle_shutdown_signal)
signal.signal(signal.SIGINT, handle_shutdown_signal)


if __name__ == "__main__":
    # Start the worker
    # In production, use: celery -A celery_app.celery worker --loglevel=info
    app.start()
