"""
LLM Client Factory

Factory pattern for creating LLM clients based on configuration.
This allows runtime selection of LLM backends without code changes.
"""

import logging
from typing import Optional

from .base import LLMClient
from .llamacpp_client import LlamaCppClient
from .vllm_client import VLLMClient

logger = logging.getLogger(__name__)


def create_llm_client(
    backend: str,
    base_url: str,
    model: Optional[str] = None,
    timeout: int = 120,
    max_retries: int = 3,
) -> LLMClient:
    """
    Create an LLM client based on the specified backend type.

    This factory function allows runtime selection of LLM backends through
    configuration. Both backends implement the same interface, making them
    interchangeable.

    Args:
        backend: Backend type ("llamacpp" or "vllm")
        base_url: Base URL of the LLM server
        model: Model name/path (optional, can be set per request)
        timeout: Request timeout in seconds (default: 120)
        max_retries: Maximum retry attempts for transient failures (default: 3)

    Returns:
        Configured LLM client instance

    Raises:
        ValueError: If backend type is not recognized

    Example:
        # Create llama.cpp client
        client = create_llm_client(
            backend="llamacpp",
            base_url="http://llm-server:8000",
            model="mistral-7b-instruct-v0.2.Q4_K_M.gguf"
        )

        # Create vLLM client
        client = create_llm_client(
            backend="vllm",
            base_url="http://llm-server:8000",
            model="mistralai/Mistral-7B-Instruct-v0.2"
        )

        # Use the client (same interface for both)
        response = await client.generate("Hello, world!")
        print(response.text)
    """
    backend_lower = backend.lower()

    logger.info(
        f"Creating LLM client: backend={backend_lower}, "
        f"base_url={base_url}, model={model}"
    )

    if backend_lower == "llamacpp":
        return LlamaCppClient(
            base_url=base_url,
            model=model,
            timeout=timeout,
            max_retries=max_retries,
        )
    elif backend_lower == "vllm":
        return VLLMClient(
            base_url=base_url,
            model=model,
            timeout=timeout,
            max_retries=max_retries,
        )
    else:
        available_backends = ["llamacpp", "vllm"]
        raise ValueError(
            f"Unknown backend: {backend}. "
            f"Available backends: {', '.join(available_backends)}"
        )


def create_llm_client_from_config(config: dict) -> LLMClient:
    """
    Create an LLM client from a configuration dictionary.

    This is useful when loading configuration from environment variables,
    config files, or a settings management system.

    Args:
        config: Configuration dictionary with keys:
            - backend (str): Backend type ("llamacpp" or "vllm")
            - base_url (str): LLM server base URL
            - model (str, optional): Model name
            - timeout (int, optional): Request timeout in seconds
            - max_retries (int, optional): Max retry attempts

    Returns:
        Configured LLM client instance

    Raises:
        ValueError: If required config keys are missing or invalid

    Example:
        config = {
            "backend": "vllm",
            "base_url": "http://llm-server:8000",
            "model": "mistralai/Mistral-7B-Instruct-v0.2",
            "timeout": 120,
            "max_retries": 3
        }

        client = create_llm_client_from_config(config)
        response = await client.generate("Explain AI")
    """
    required_keys = ["backend", "base_url"]
    missing_keys = [key for key in required_keys if key not in config]

    if missing_keys:
        raise ValueError(
            f"Missing required configuration keys: {', '.join(missing_keys)}"
        )

    return create_llm_client(
        backend=config["backend"],
        base_url=config["base_url"],
        model=config.get("model"),
        timeout=config.get("timeout", 120),
        max_retries=config.get("max_retries", 3),
    )
