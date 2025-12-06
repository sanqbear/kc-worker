"""
Retry utilities with exponential backoff and error classification.

Provides intelligent retry logic that:
- Uses exponential backoff to avoid thundering herd
- Classifies errors into retryable vs non-retryable
- Respects maximum retry limits
- Includes jitter to prevent synchronized retries
"""

import random
from typing import Optional, Type, Union

from celery.exceptions import Reject


def exponential_backoff(
    retry_count: int,
    base_delay: int = 60,
    max_delay: int = 3600,
    jitter: bool = True
) -> int:
    """
    Calculate exponential backoff delay with optional jitter.

    Formula: min(base_delay * 2^retry_count, max_delay) ± jitter

    Args:
        retry_count: Current retry attempt number (0-indexed)
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        jitter: Whether to add random jitter (±25%)

    Returns:
        int: Delay in seconds before next retry
    """
    delay = min(base_delay * (2 ** retry_count), max_delay)

    if jitter:
        # Add ±25% jitter to prevent synchronized retries
        jitter_range = delay * 0.25
        delay = delay + random.uniform(-jitter_range, jitter_range)

    return int(delay)


class RetryableError(Exception):
    """Base class for errors that should trigger retries."""
    pass


class NonRetryableError(Exception):
    """Base class for errors that should NOT trigger retries."""
    pass


# Specific retryable errors
class LLMServerError(RetryableError):
    """LLM server returned 5xx error (transient failure)."""
    pass


class LLMTimeoutError(RetryableError):
    """LLM request timed out."""
    pass


class RateLimitError(RetryableError):
    """Hit rate limit, should retry after backoff."""
    pass


class ConnectionError(RetryableError):
    """Network connection error (DNS, TCP, etc)."""
    pass


# Specific non-retryable errors
class InvalidInputError(NonRetryableError):
    """Invalid task input that won't succeed on retry."""
    pass


class LLMClientError(NonRetryableError):
    """LLM server returned 4xx error (client error)."""
    pass


class AuthenticationError(NonRetryableError):
    """Authentication failed (invalid API key, etc)."""
    pass


class SchemaValidationError(NonRetryableError):
    """Output failed schema validation."""
    pass


def should_retry(exc: Exception) -> bool:
    """
    Determine if an exception should trigger a retry.

    Args:
        exc: The exception that was raised

    Returns:
        bool: True if the task should be retried, False otherwise
    """
    # Check if it's explicitly marked as retryable
    if isinstance(exc, RetryableError):
        return True

    # Check if it's explicitly marked as non-retryable
    if isinstance(exc, NonRetryableError):
        return False

    # Default: retry on common transient errors
    retryable_exceptions = (
        # Network errors
        ConnectionError,
        TimeoutError,
        OSError,  # Includes network-related OS errors

        # HTTP errors (we'll check status codes in task logic)
        Exception,  # Default to retrying unknown exceptions
    )

    non_retryable_exceptions = (
        # Input validation errors
        ValueError,
        TypeError,
        KeyError,
        AttributeError,

        # Celery control exceptions
        Reject,
    )

    # Check non-retryable first (more specific)
    if isinstance(exc, non_retryable_exceptions):
        return False

    if isinstance(exc, retryable_exceptions):
        return True

    # Unknown exception type: default to not retrying
    return False


def classify_http_error(status_code: int) -> Type[Exception]:
    """
    Classify HTTP error by status code into retryable vs non-retryable.

    Args:
        status_code: HTTP status code

    Returns:
        Type[Exception]: Exception class to raise
    """
    if status_code == 429:
        return RateLimitError
    elif 400 <= status_code < 500:
        # Client errors (except 429) are non-retryable
        if status_code == 401 or status_code == 403:
            return AuthenticationError
        return LLMClientError
    elif 500 <= status_code < 600:
        # Server errors are retryable
        return LLMServerError
    else:
        # Unknown status code, treat as retryable
        return RetryableError
