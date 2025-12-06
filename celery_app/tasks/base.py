"""
Base task class with common LLM processing logic.

Provides a template method pattern for tasks that:
1. Build a prompt from input
2. Call the LLM
3. Postprocess the result

All tasks inherit from BaseLLMTask and implement the abstract methods.
"""

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import aiohttp
from celery import Task
from celery.exceptions import Reject

from ..celery import app
from ..config import settings
from ..utils.logging import bind_task_context, get_logger, unbind_task_context
from ..utils.retry import (
    LLMClientError,
    LLMServerError,
    LLMTimeoutError,
    InvalidInputError,
    exponential_backoff,
    should_retry,
    classify_http_error,
)


logger = get_logger(__name__)


class BaseLLMTask(Task, ABC):
    """
    Base class for all LLM-based tasks.

    Provides:
    - LLM client initialization and lifecycle management
    - Common error handling with retry logic
    - Structured logging with task context
    - Template method for prompt → LLM → postprocess workflow
    """

    # Class-level session (reused across task executions)
    _session: Optional[aiohttp.ClientSession] = None

    def __init__(self) -> None:
        """Initialize the base task."""
        super().__init__()
        self.logger = get_logger(self.__class__.__name__)

    @property
    def session(self) -> aiohttp.ClientSession:
        """
        Get or create an aiohttp session for LLM API calls.

        Returns:
            aiohttp.ClientSession: HTTP session with timeout configuration
        """
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(
                total=settings.task_soft_time_limit,
                connect=10,
                sock_read=settings.task_soft_time_limit - 10
            )
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers={"Content-Type": "application/json"}
            )
        return self._session

    async def close_session(self) -> None:
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    @abstractmethod
    def build_prompt(self, **kwargs: Any) -> str:
        """
        Build the prompt for the LLM from task inputs.

        Args:
            **kwargs: Task input parameters

        Returns:
            str: The formatted prompt

        Raises:
            InvalidInputError: If input validation fails
        """
        pass

    @abstractmethod
    def postprocess(self, llm_output: str, **kwargs: Any) -> Dict[str, Any]:
        """
        Postprocess the LLM output into the final task result.

        Args:
            llm_output: Raw output from the LLM
            **kwargs: Original task input parameters

        Returns:
            Dict[str, Any]: Processed task result

        Raises:
            InvalidInputError: If postprocessing fails
        """
        pass

    async def call_llm(self, prompt: str, **generation_params: Any) -> str:
        """
        Call the LLM inference server.

        This method handles:
        - Request construction based on backend type (llamacpp vs vllm)
        - HTTP error handling with classification
        - Response parsing

        Args:
            prompt: The prompt to send to the LLM
            **generation_params: Additional generation parameters

        Returns:
            str: The generated text from the LLM

        Raises:
            LLMServerError: On 5xx errors (retryable)
            LLMClientError: On 4xx errors (non-retryable)
            LLMTimeoutError: On timeout (retryable)
            InvalidInputError: On malformed response (non-retryable)
        """
        # Merge default parameters with task-specific overrides
        params = {
            "max_tokens": settings.max_tokens,
            "temperature": settings.temperature,
            "top_p": settings.top_p,
            "top_k": settings.top_k,
            **generation_params
        }

        # Build request payload based on backend type
        if settings.llm_backend == "llamacpp":
            endpoint = f"{settings.llm_server_url}/completion"
            payload = {
                "prompt": prompt,
                "n_predict": params["max_tokens"],
                "temperature": params["temperature"],
                "top_p": params["top_p"],
                "top_k": params["top_k"],
                "stop": params.get("stop", []),
            }
        elif settings.llm_backend == "vllm":
            endpoint = f"{settings.llm_server_url}/v1/completions"
            payload = {
                "model": settings.llm_model,
                "prompt": prompt,
                "max_tokens": params["max_tokens"],
                "temperature": params["temperature"],
                "top_p": params["top_p"],
                "stop": params.get("stop", []),
            }
        else:
            raise InvalidInputError(f"Unsupported LLM backend: {settings.llm_backend}")

        self.logger.debug(
            "Calling LLM API",
            extra={
                "endpoint": endpoint,
                "backend": settings.llm_backend,
                "prompt_length": len(prompt),
            }
        )

        try:
            async with self.session.post(endpoint, json=payload) as response:
                # Check for HTTP errors
                if response.status != 200:
                    error_text = await response.text()
                    self.logger.warning(
                        "LLM API returned error",
                        extra={
                            "status_code": response.status,
                            "error": error_text,
                        }
                    )
                    error_class = classify_http_error(response.status)
                    raise error_class(f"LLM API error: {response.status} - {error_text}")

                # Parse response
                data = await response.json()

                # Extract generated text based on backend format
                if settings.llm_backend == "llamacpp":
                    if "content" not in data:
                        raise InvalidInputError(f"Unexpected llamacpp response format: {data}")
                    return data["content"]
                elif settings.llm_backend == "vllm":
                    if "choices" not in data or len(data["choices"]) == 0:
                        raise InvalidInputError(f"Unexpected vllm response format: {data}")
                    return data["choices"][0]["text"]
                else:
                    raise InvalidInputError(f"Unsupported backend: {settings.llm_backend}")

        except aiohttp.ClientError as e:
            self.logger.error("LLM API connection error", extra={"error": str(e)})
            raise LLMServerError(f"Connection error: {e}") from e
        except asyncio.TimeoutError as e:
            self.logger.error("LLM API timeout", extra={"timeout": settings.task_soft_time_limit})
            raise LLMTimeoutError(f"Request timeout after {settings.task_soft_time_limit}s") from e
        except json.JSONDecodeError as e:
            self.logger.error("Failed to parse LLM response", extra={"error": str(e)})
            raise InvalidInputError(f"Invalid JSON response: {e}") from e

    def run(self, **kwargs: Any) -> Dict[str, Any]:
        """
        Execute the task (synchronous Celery entry point).

        This method wraps the async execution and handles the complete lifecycle:
        1. Bind task context for logging
        2. Validate inputs
        3. Build prompt
        4. Call LLM
        5. Postprocess result
        6. Cleanup

        Args:
            **kwargs: Task input parameters

        Returns:
            Dict[str, Any]: Task result

        Raises:
            Various exceptions based on failure mode
        """
        # Bind task context for structured logging
        bind_task_context(
            task_id=self.request.id,
            task_name=self.name,
        )

        try:
            self.logger.info(
                "Task started",
                extra={"input_keys": list(kwargs.keys())}
            )

            # Run async workflow
            import asyncio
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(self._async_run(**kwargs))

            self.logger.info("Task completed successfully")
            return result

        except Exception as e:
            self.logger.error(
                "Task failed",
                extra={"error": str(e), "error_type": type(e).__name__}
            )
            raise

        finally:
            # Cleanup
            unbind_task_context()

    async def _async_run(self, **kwargs: Any) -> Dict[str, Any]:
        """
        Async implementation of the task workflow.

        Args:
            **kwargs: Task input parameters

        Returns:
            Dict[str, Any]: Task result
        """
        try:
            # Step 1: Build prompt
            prompt = self.build_prompt(**kwargs)

            # Step 2: Call LLM
            llm_output = await self.call_llm(prompt)

            # Step 3: Postprocess
            result = self.postprocess(llm_output, **kwargs)

            return result

        finally:
            # Ensure session is closed
            await self.close_session()

    def on_retry(self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo: Any) -> None:
        """
        Called when a task is retried.

        Args:
            exc: The exception that caused the retry
            task_id: Unique task identifier
            args: Task positional arguments
            kwargs: Task keyword arguments
            einfo: Exception info
        """
        self.logger.warning(
            "Task retrying",
            extra={
                "task_id": task_id,
                "retry_count": self.request.retries,
                "max_retries": self.max_retries,
                "exception": str(exc),
            }
        )

    def on_failure(self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo: Any) -> None:
        """
        Called when a task fails after all retries.

        Args:
            exc: The exception that caused the failure
            task_id: Unique task identifier
            args: Task positional arguments
            kwargs: Task keyword arguments
            einfo: Exception info
        """
        self.logger.error(
            "Task failed permanently",
            extra={
                "task_id": task_id,
                "exception": str(exc),
                "traceback": str(einfo),
            }
        )

    def autoretry_for(self, exc: Exception) -> bool:
        """
        Determine if a task should be retried for a given exception.

        Args:
            exc: The exception that was raised

        Returns:
            bool: True if the task should be retried
        """
        return should_retry(exc)


# Import asyncio here to avoid circular imports
import asyncio
