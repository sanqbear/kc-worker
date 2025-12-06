"""
LLM Client Abstraction Layer

This package provides a unified interface for interacting with different LLM backends
(llama.cpp and vLLM) through their OpenAI-compatible APIs.

Usage:
    from llm import create_llm_client, LLMResponse

    client = create_llm_client(
        backend="llamacpp",
        base_url="http://llm-server:8000",
        model="mistral-7b"
    )

    # Async usage
    response = await client.generate("Hello, world!")
    print(response.text)

    # Sync usage (for Celery tasks)
    response = client.generate_sync("Hello, world!")
    print(response.text)
"""

from .base import LLMClient
from .factory import create_llm_client
from .llamacpp_client import LlamaCppClient
from .response import LLMResponse, LLMUsage
from .vllm_client import VLLMClient

__all__ = [
    "LLMClient",
    "LLMResponse",
    "LLMUsage",
    "LlamaCppClient",
    "VLLMClient",
    "create_llm_client",
]

__version__ = "0.1.0"
