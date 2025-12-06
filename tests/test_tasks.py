"""
Tests for Celery tasks.
"""
import pytest
from unittest.mock import patch, MagicMock

from llm.response import LLMResponse


class TestSummarizeTask:
    """Tests for summarization task."""

    def test_summarize_task(self, mock_llm_client, sample_text_korean):
        """Test summarization task execution."""
        # Mock the LLM response for summarization
        mock_llm_client.generate_sync.return_value = LLMResponse(
            text="인공지능(AI)은 인간의 지능을 인공적으로 구현한 컴퓨터 시스템이다.",
            usage={"prompt_tokens": 100, "completion_tokens": 30, "total_tokens": 130},
            model="test-model",
            finish_reason="stop"
        )

        with patch('celery_app.tasks.summarize.get_llm_client', return_value=mock_llm_client):
            from celery_app.tasks.summarize import summarize_task

            result = summarize_task.apply(args=[{
                "text": sample_text_korean,
                "max_length": 100
            }]).get()

            assert "summary" in result
            assert "original_length" in result
            assert "summary_length" in result
            assert result["summary_length"] <= result["original_length"]


class TestKeywordsTask:
    """Tests for keyword extraction task."""

    def test_keywords_task(self, mock_llm_client, sample_text_korean):
        """Test keyword extraction task execution."""
        # Mock the LLM response for keywords
        mock_llm_client.generate_sync.return_value = LLMResponse(
            text='["인공지능", "컴퓨터", "학습", "추론", "정보기술"]',
            usage={"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
            model="test-model",
            finish_reason="stop"
        )

        with patch('celery_app.tasks.keywords.get_llm_client', return_value=mock_llm_client):
            from celery_app.tasks.keywords import keywords_task

            result = keywords_task.apply(args=[{
                "text": sample_text_korean,
                "max_keywords": 5
            }]).get()

            assert "keywords" in result
            assert "count" in result
            assert isinstance(result["keywords"], list)
            assert result["count"] <= 5


class TestNormalizeTask:
    """Tests for JSON normalization task."""

    def test_normalize_task(self, mock_llm_client, sample_normalize_request):
        """Test normalization task execution."""
        # Mock the LLM response for normalization
        mock_llm_client.generate_sync.return_value = LLMResponse(
            text='{"action": "예약", "date": "내일", "time": "15:00", "location": "회의실 A", "participants": ["마케팅 팀"]}',
            usage={"prompt_tokens": 150, "completion_tokens": 50, "total_tokens": 200},
            model="test-model",
            finish_reason="stop"
        )

        with patch('celery_app.tasks.normalize.get_llm_client', return_value=mock_llm_client):
            from celery_app.tasks.normalize import normalize_task

            result = normalize_task.apply(args=[sample_normalize_request]).get()

            assert "normalized" in result
            assert "confidence" in result
            assert isinstance(result["normalized"], dict)
            assert 0 <= result["confidence"] <= 1


class TestTaskErrorHandling:
    """Tests for task error handling."""

    def test_summarize_empty_text(self, mock_llm_client):
        """Test summarization with empty text."""
        with patch('celery_app.tasks.summarize.get_llm_client', return_value=mock_llm_client):
            from celery_app.tasks.summarize import summarize_task

            with pytest.raises(ValueError, match="text"):
                summarize_task.apply(args=[{"text": ""}]).get()

    def test_keywords_empty_text(self, mock_llm_client):
        """Test keyword extraction with empty text."""
        with patch('celery_app.tasks.keywords.get_llm_client', return_value=mock_llm_client):
            from celery_app.tasks.keywords import keywords_task

            with pytest.raises(ValueError, match="text"):
                keywords_task.apply(args=[{"text": ""}]).get()

    def test_normalize_missing_schema(self, mock_llm_client):
        """Test normalization with missing schema."""
        with patch('celery_app.tasks.normalize.get_llm_client', return_value=mock_llm_client):
            from celery_app.tasks.normalize import normalize_task

            with pytest.raises(ValueError, match="schema"):
                normalize_task.apply(args=[{
                    "request": "테스트 요청"
                }]).get()
