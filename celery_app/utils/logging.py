"""
Structured logging configuration for the worker service.

Provides JSON and text logging formats with contextual information including:
- Correlation IDs for request tracing
- Task metadata (task_id, task_name)
- Environment and service information
"""

import logging
import sys
from typing import Any, Dict, Optional

import structlog
from structlog.typing import EventDict, Processor

from ..config import settings


def add_service_context(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """
    Add service-level context to all log entries.

    Args:
        logger: The logger instance
        method_name: The name of the method being called
        event_dict: The event dictionary

    Returns:
        EventDict: Updated event dictionary with service context
    """
    event_dict["service"] = "worker"
    event_dict["environment"] = settings.environment
    return event_dict


def setup_logging() -> structlog.BoundLogger:
    """
    Configure structured logging for the application.

    Returns:
        structlog.BoundLogger: Configured logger instance
    """
    # Configure shared processors for both structlog and stdlib
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.ExtraAdder(),
        add_service_context,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.log_format == "json":
        # JSON output for production
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Human-readable console output for development
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.log_level)
        ),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.getLevelName(settings.log_level),
    )

    # Set log levels for third-party libraries
    logging.getLogger("celery").setLevel(logging.WARNING)
    logging.getLogger("kombu").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)

    return structlog.get_logger()


def get_logger(name: Optional[str] = None) -> structlog.BoundLogger:
    """
    Get a logger instance with optional name.

    Args:
        name: Optional logger name (typically __name__)

    Returns:
        structlog.BoundLogger: Logger instance
    """
    if name:
        return structlog.get_logger(name)
    return structlog.get_logger()


def bind_task_context(task_id: str, task_name: str, **kwargs: Any) -> None:
    """
    Bind task context to the logger for correlation.

    This adds task-specific context to all subsequent log entries in the current context.

    Args:
        task_id: Unique task identifier
        task_name: Name of the task
        **kwargs: Additional context to bind
    """
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        task_id=task_id,
        task_name=task_name,
        **kwargs
    )


def unbind_task_context() -> None:
    """
    Clear task context from the logger.

    Should be called in task cleanup to prevent context bleeding between tasks.
    """
    structlog.contextvars.clear_contextvars()
