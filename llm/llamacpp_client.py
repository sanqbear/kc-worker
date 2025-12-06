"""
llama.cpp Client Implementation

Client for llama.cpp server with OpenAI-compatible API.
Supports both async and sync operations for different worker contexts.
"""

import asyncio
import logging
from typing import Any, Optional

import httpx

from .base import LLMClient
from .response import (
    LLMConnectionError,
    LLMResponse,
    LLMServerError,
    LLMTimeoutError,
    LLMUsage,
)

logger = logging.getLogger(__name__)


class LlamaCppClient(LLMClient):
    """
    Client for llama.cpp server with OpenAI-compatible API.

    The llama.cpp server exposes an OpenAI-compatible endpoint at /v1/completions.
    This client handles request formatting, error handling, and response parsing.

    Example:
        client = LlamaCppClient(
            base_url="http://llm-server:8000",
            model="mistral-7b-instruct-v0.2.Q4_K_M.gguf"
        )

        # Async
        response = await client.generate("What is Python?")
        print(response.text)

        # Sync (for Celery)
        response = client.generate_sync("What is Python?")
        print(response.text)
    """

    def __init__(
        self,
        base_url: str,
        model: Optional[str] = None,
        timeout: int = 120,
        max_retries: int = 3,
    ):
        """
        Initialize llama.cpp client.

        Args:
            base_url: Base URL of llama.cpp server (e.g., "http://llm-server:8000")
            model: Model file name (optional)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts for transient failures
        """
        super().__init__(base_url, model, timeout)
        self.max_retries = max_retries
        self.completions_url = f"{self.base_url}/v1/completions"
        self.health_url = f"{self.base_url}/health"

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
        Generate text asynchronously using llama.cpp.

        Args:
            prompt: Input prompt text
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0 = deterministic, 2.0 = very random)
            top_p: Nucleus sampling threshold
            stop: List of sequences that stop generation
            model: Model override (uses default if not specified)
            **kwargs: Additional llama.cpp-specific parameters

        Returns:
            LLMResponse with generated text and metadata

        Raises:
            LLMConnectionError: Cannot connect to server
            LLMTimeoutError: Request timeout
            LLMServerError: Server returned error
        """
        self._validate_parameters(prompt, max_tokens, temperature, top_p)
        model_name = self._get_model_name(model)

        payload = {
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "stop": stop or [],
            **kwargs,
        }

        # Only include model if llama.cpp supports it
        # Some llama.cpp servers ignore this field
        if model_name:
            payload["model"] = model_name

        logger.debug(
            f"llama.cpp generate request: max_tokens={max_tokens}, "
            f"temperature={temperature}, model={model_name}"
        )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    self.completions_url,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

                return self._parse_response(data, model_name)

            except httpx.TimeoutException as e:
                logger.error(f"llama.cpp request timeout: {e}")
                raise LLMTimeoutError(f"Request timed out after {self.timeout}s")

            except httpx.ConnectError as e:
                logger.error(f"llama.cpp connection error: {e}")
                raise LLMConnectionError(
                    f"Cannot connect to llama.cpp server at {self.base_url}"
                )

            except httpx.HTTPStatusError as e:
                logger.error(f"llama.cpp HTTP error: {e.response.status_code} - {e}")
                error_detail = e.response.text
                raise LLMServerError(
                    f"Server error: {error_detail}", status_code=e.response.status_code
                )

            except Exception as e:
                logger.error(f"llama.cpp unexpected error: {e}", exc_info=True)
                raise LLMServerError(f"Unexpected error: {str(e)}")

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
        Generate text synchronously (for Celery tasks).

        This is a blocking wrapper around the async generate method.
        Use this in synchronous contexts like Celery workers.
        """
        return asyncio.run(
            self.generate(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                stop=stop,
                model=model,
                **kwargs,
            )
        )

    async def health_check(self) -> bool:
        """
        Check if llama.cpp server is healthy.

        Returns:
            True if server responds to health endpoint, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.health_url)
                is_healthy = response.status_code == 200

                if is_healthy:
                    logger.debug("llama.cpp health check: OK")
                else:
                    logger.warning(
                        f"llama.cpp health check failed: status={response.status_code}"
                    )

                return is_healthy

        except Exception as e:
            logger.warning(f"llama.cpp health check error: {e}")
            return False

    def health_check_sync(self) -> bool:
        """
        Check if llama.cpp server is healthy (synchronous).

        Returns:
            True if server is healthy, False otherwise
        """
        return asyncio.run(self.health_check())

    def _parse_response(self, data: dict, model_name: str) -> LLMResponse:
        """
        Parse llama.cpp response into LLMResponse model.

        Args:
            data: Raw JSON response from llama.cpp
            model_name: Model name used for request

        Returns:
            Parsed LLMResponse

        Raises:
            LLMServerError: If response format is invalid
        """
        try:
            # llama.cpp OpenAI-compatible format
            choices = data.get("choices", [])
            if not choices:
                raise LLMServerError("No choices in response")

            first_choice = choices[0]
            text = first_choice.get("text", "")
            finish_reason = first_choice.get("finish_reason", "unknown")

            # Parse usage statistics
            usage_data = data.get("usage", {})
            usage = LLMUsage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
            )

            # Get model from response or use provided name
            response_model = data.get("model", model_name)

            return LLMResponse(
                text=text,
                usage=usage,
                model=response_model,
                finish_reason=finish_reason,
                request_id=data.get("id"),
            )

        except (KeyError, TypeError, ValueError) as e:
            logger.error(f"Failed to parse llama.cpp response: {e}", exc_info=True)
            raise LLMServerError(f"Invalid response format: {str(e)}")
