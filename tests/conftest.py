"""
Pytest configuration and fixtures for worker tests.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from llm.response import LLMResponse


@pytest.fixture
def mock_llm_response():
    """Create a mock LLM response."""
    return LLMResponse(
        text="This is a test response",
        usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        model="test-model",
        finish_reason="stop"
    )


@pytest.fixture
def mock_llm_client(mock_llm_response):
    """Create a mock LLM client."""
    client = MagicMock()
    client.generate_sync.return_value = mock_llm_response
    client.generate = AsyncMock(return_value=mock_llm_response)
    client.health_check = AsyncMock(return_value=True)
    return client


@pytest.fixture
def sample_text_korean():
    """Sample Korean text for testing."""
    return """
    인공지능(AI)은 인간의 학습능력, 추론능력, 지각능력을 인공적으로 구현한
    컴퓨터 프로그램 또는 이를 포함한 컴퓨터 시스템이다. 하나의 인프라 기술이기도 하다.
    인공지능은 그 자체로 존재하는 것이 아니라, 컴퓨터 과학의 다른 분야와 직간접으로
    많은 관련을 맺고 있다. 특히 현대에는 정보기술의 여러 분야에서 인공지능적 요소를
    도입하여 그 분야의 문제 풀이에 활용하려는 시도가 매우 활발하게 이루어지고 있다.
    """


@pytest.fixture
def sample_text_english():
    """Sample English text for testing."""
    return """
    Artificial intelligence (AI) is the simulation of human intelligence processes
    by machines, especially computer systems. Specific applications of AI include
    expert systems, natural language processing, speech recognition and machine vision.
    AI programming focuses on cognitive skills that include learning, reasoning,
    self-correction, and creativity.
    """


@pytest.fixture
def sample_normalize_request():
    """Sample normalization request for testing."""
    return {
        "request": "내일 오후 3시에 회의실 A에서 마케팅 팀 회의 예약해줘",
        "schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string"},
                "date": {"type": "string"},
                "time": {"type": "string"},
                "location": {"type": "string"},
                "participants": {"type": "array", "items": {"type": "string"}}
            }
        }
    }
