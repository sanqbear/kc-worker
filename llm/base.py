"""
Abstract Base Class for LLM Clients

Defines the interface that all LLM backend implementations must follow.
This ensures consistency across different backends (llama.cpp, vLLM, etc.)
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from .response import LLMResponse


class LLMClient(ABC):
    """
    Abstract base class for LLM backend clients.

    All LLM implementations must inherit from this class and implement
    the required methods. This ensures a consistent interface regardless
    of the underlying backend.

    Attributes:
        base_url: Base URL of the LLM server (e.g., "http://llm-server:8000")
        model: Model name to use for generation (optional, can be set per request)
        timeout: Default timeout for requests in seconds
    """

    def __init__(
        self,
        base_url: str,
        model: Optional[str] = None,
        timeout: int = 120,
    ):
        """
        Initialize the LLM client.

        Args:
            base_url: Base URL of the LLM server
            model: Default model name to use (can be overridden per request)
            timeout: Request timeout in seconds (default: 120)
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        top_p: float = 1.0,
        stop: Optional[list[str]] = None,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Generate text from a prompt asynchronously.

        This method should be used in async contexts (FastAPI, asyncio workers).

        Args:
            prompt: Input text prompt
            max_tokens: Maximum number of tokens to generate
            temperature: Sampling temperature (0.0 to 2.0)
            top_p: Nucleus sampling probability
            stop: List of stop sequences
            model: Model to use (overrides default)
            **kwargs: Additional backend-specific parameters

        Returns:
            LLMResponse containing generated text and metadata

        Raises:
            LLMConnectionError: If unable to connect to server
            LLMTimeoutError: If request times out
            LLMServerError: If server returns an error
            LLMValidationError: If parameters are invalid
        """
        pass

    @abstractmethod
    def generate_sync(
        self,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        top_p: float = 1.0,
        stop: Optional[list[str]] = None,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Generate text from a prompt synchronously.

        This method should be used in synchronous contexts (Celery tasks).

        Args:
            prompt: Input text prompt
            max_tokens: Maximum number of tokens to generate
            temperature: Sampling temperature (0.0 to 2.0)
            top_p: Nucleus sampling probability
            stop: List of stop sequences
            model: Model to use (overrides default)
            **kwargs: Additional backend-specific parameters

        Returns:
            LLMResponse containing generated text and metadata

        Raises:
            LLMConnectionError: If unable to connect to server
            LLMTimeoutError: If request times out
            LLMServerError: If server returns an error
            LLMValidationError: If parameters are invalid
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the LLM server is healthy and responsive.

        This should be used for liveness/readiness probes in orchestration
        systems (Kubernetes, Docker Compose health checks).

        Returns:
            True if server is healthy, False otherwise
        """
        pass

    @abstractmethod
    def health_check_sync(self) -> bool:
        """
        Check if the LLM server is healthy (synchronous version).

        Returns:
            True if server is healthy, False otherwise
        """
        pass

    def _validate_parameters(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        top_p: float,
    ) -> None:
        """
        Validate generation parameters.

        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling probability

        Raises:
            LLMValidationError: If any parameter is invalid
        """
        from .response import LLMValidationError

        if not prompt or not prompt.strip():
            raise LLMValidationError("Prompt cannot be empty")

        if max_tokens <= 0:
            raise LLMValidationError(
                f"max_tokens must be positive, got {max_tokens}"
            )

        if not 0.0 <= temperature <= 2.0:
            raise LLMValidationError(
                f"temperature must be between 0.0 and 2.0, got {temperature}"
            )

        if not 0.0 <= top_p <= 1.0:
            raise LLMValidationError(
                f"top_p must be between 0.0 and 1.0, got {top_p}"
            )

    def _get_model_name(self, model: Optional[str] = None) -> str:
        """
        Get the model name to use for a request.

        Args:
            model: Optional model name override

        Returns:
            Model name to use

        Raises:
            LLMValidationError: If no model is specified
        """
        from .response import LLMValidationError

        result_model = model or self.model
        if not result_model:
            raise LLMValidationError(
                "No model specified. Provide model in constructor or method call."
            )
        return result_model
