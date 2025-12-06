"""
Tests for LLM client implementations.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import httpx

from llm.response import LLMResponse
from llm.factory import create_llm_client


class TestLLMResponse:
    """Tests for LLMResponse model."""

    def test_create_response(self):
        """Test creating an LLM response."""
        response = LLMResponse(
            text="Hello, world!",
            usage={"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
            model="test-model",
            finish_reason="stop"
        )

        assert response.text == "Hello, world!"
        assert response.usage["total_tokens"] == 8
        assert response.model == "test-model"
        assert response.finish_reason == "stop"


class TestLLMClientFactory:
    """Tests for LLM client factory."""

    def test_create_llamacpp_client(self):
        """Test creating llama.cpp client."""
        client = create_llm_client(
            backend="llamacpp",
            base_url="http://localhost:8000",
            model="test-model"
        )

        assert client is not None
        assert client.base_url == "http://localhost:8000"
        assert client.model == "test-model"

    def test_create_vllm_client(self):
        """Test creating vLLM client."""
        client = create_llm_client(
            backend="vllm",
            base_url="http://localhost:8000",
            model="test-model"
        )

        assert client is not None
        assert client.base_url == "http://localhost:8000"

    def test_invalid_backend(self):
        """Test creating client with invalid backend."""
        with pytest.raises(ValueError, match="Unknown backend"):
            create_llm_client(
                backend="invalid",
                base_url="http://localhost:8000"
            )


class TestLlamaCppClient:
    """Tests for llama.cpp client."""

    @pytest.fixture
    def client(self):
        """Create a llama.cpp client for testing."""
        return create_llm_client(
            backend="llamacpp",
            base_url="http://localhost:8000",
            model="test-model"
        )

    def test_generate_sync(self, client):
        """Test synchronous generation."""
        mock_response = {
            "choices": [
                {
                    "text": "Generated text",
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15
            },
            "model": "test-model"
        }

        with patch.object(client, '_sync_client') as mock_client:
            mock_client.post.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_response,
                raise_for_status=lambda: None
            )

            response = client.generate_sync("Test prompt")

            assert response.text == "Generated text"
            assert response.finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, client):
        """Test health check when server is healthy."""
        with patch.object(client, '_async_client') as mock_client:
            mock_client.get = AsyncMock(return_value=MagicMock(
                status_code=200
            ))

            result = await client.health_check()

            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, client):
        """Test health check when server is down."""
        with patch.object(client, '_async_client') as mock_client:
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

            result = await client.health_check()

            assert result is False


class TestVLLMClient:
    """Tests for vLLM client."""

    @pytest.fixture
    def client(self):
        """Create a vLLM client for testing."""
        return create_llm_client(
            backend="vllm",
            base_url="http://localhost:8000",
            model="test-model"
        )

    def test_generate_sync(self, client):
        """Test synchronous generation."""
        mock_response = {
            "choices": [
                {
                    "text": "Generated text from vLLM",
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15
            },
            "model": "test-model"
        }

        with patch.object(client, '_sync_client') as mock_client:
            mock_client.post.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_response,
                raise_for_status=lambda: None
            )

            response = client.generate_sync("Test prompt")

            assert response.text == "Generated text from vLLM"
