"""Unit tests for prompt templates."""

import pytest
from llm.prompts import SummarizePrompt, KeywordsPrompt, NormalizePrompt


class TestSummarizePrompt:
    """Test cases for SummarizePrompt."""

    def test_build_basic(self):
        """Test basic prompt building."""
        prompt = SummarizePrompt()
        text = "이것은 테스트 텍스트입니다."

        result = prompt.build(text=text)

        assert "다음 텍스트를 요약해주세요" in result
        assert text in result
        assert "원문 시작" in result

    def test_build_with_max_length(self):
        """Test prompt with max_length constraint."""
        prompt = SummarizePrompt()
        text = "이것은 테스트 텍스트입니다."

        result = prompt.build(text=text, max_length=100)

        assert "최대 100자" in result
        assert text in result

    def test_build_with_context(self):
        """Test prompt with context information."""
        prompt = SummarizePrompt()
        text = "이것은 티켓 내용입니다."

        result = prompt.build_with_context(
            text=text,
            max_length=50,
            context="티켓 내용"
        )

        assert "티켓 내용" in result
        assert "최대 50자" in result
        assert text in result

    def test_build_empty_text_raises_error(self):
        """Test that empty text raises ValueError."""
        prompt = SummarizePrompt()

        with pytest.raises(ValueError, match="Text to summarize cannot be empty"):
            prompt.build(text="")

    def test_build_none_text_raises_error(self):
        """Test that None text raises ValueError."""
        prompt = SummarizePrompt()

        with pytest.raises(ValueError, match="Missing required parameters"):
            prompt.build(text=None)

    def test_system_prompt_exists(self):
        """Test that system prompt is defined."""
        prompt = SummarizePrompt()

        system = prompt.system_prompt

        assert system
        assert "요약" in system
        assert "한국어" in system


class TestKeywordsPrompt:
    """Test cases for KeywordsPrompt."""

    def test_build_basic(self):
        """Test basic keyword extraction prompt."""
        prompt = KeywordsPrompt()
        text = "Vue 3와 TypeScript를 사용한 프로젝트입니다."

        result = prompt.build(text=text, max_keywords=5)

        assert "5개 이하로 추출" in result
        assert text in result
        assert "JSON 배열" in result

    def test_build_with_domain(self):
        """Test prompt with domain context."""
        prompt = KeywordsPrompt()
        text = "React와 Redux를 사용합니다."

        result = prompt.build_with_domain(
            text=text,
            max_keywords=10,
            domain="프론트엔드 개발"
        )

        assert "프론트엔드 개발" in result
        assert "10개 이하로 추출" in result
        assert text in result

    def test_build_multilingual(self):
        """Test prompt with multilingual support."""
        prompt = KeywordsPrompt()
        text = "Python and TypeScript development."

        result = prompt.build_multilingual(
            text=text,
            max_keywords=8,
            include_english=True
        )

        assert "한국어와 영어" in result
        assert text in result

    def test_build_empty_text_raises_error(self):
        """Test that empty text raises ValueError."""
        prompt = KeywordsPrompt()

        with pytest.raises(ValueError, match="cannot be empty"):
            prompt.build(text="   ")

    def test_build_invalid_max_keywords(self):
        """Test that invalid max_keywords raises ValueError."""
        prompt = KeywordsPrompt()

        with pytest.raises(ValueError, match="must be at least 1"):
            prompt.build(text="test", max_keywords=0)

    def test_system_prompt_exists(self):
        """Test that system prompt is defined."""
        prompt = KeywordsPrompt()

        system = prompt.system_prompt

        assert system
        assert "키워드" in system
        assert "JSON 배열" in system


class TestNormalizePrompt:
    """Test cases for NormalizePrompt."""

    def test_build_basic(self):
        """Test basic normalization prompt."""
        prompt = NormalizePrompt()
        text = "이름은 김철수이고 이메일은 kim@example.com입니다."
        schema = {
            "name": "string",
            "email": "string"
        }

        result = prompt.build(text=text, schema=schema)

        assert text in result
        assert "name" in result
        assert "email" in result
        assert "JSON 스키마" in result

    def test_build_with_examples(self):
        """Test prompt with examples."""
        prompt = NormalizePrompt()
        text = "홍길동, hong@test.com"
        schema = {"name": "string", "email": "string"}
        examples = [
            {
                "input": "김철수, kim@example.com",
                "output": {"name": "김철수", "email": "kim@example.com"}
            }
        ]

        result = prompt.build_with_examples(
            text=text,
            schema=schema,
            examples=examples
        )

        assert text in result
        assert "예시" in result
        assert "김철수" in result

    def test_build_with_field_descriptions(self):
        """Test prompt with field descriptions."""
        prompt = NormalizePrompt()
        text = "김철수, IT 부서"
        schema = {"name": "string", "department": "string"}
        descriptions = {
            "name": "사용자 이름",
            "department": "소속 부서"
        }

        result = prompt.build_with_field_descriptions(
            text=text,
            schema=schema,
            field_descriptions=descriptions
        )

        assert text in result
        assert "필드 설명" in result
        assert "사용자 이름" in result
        assert "소속 부서" in result

    def test_build_empty_text_raises_error(self):
        """Test that empty text raises ValueError."""
        prompt = NormalizePrompt()
        schema = {"field": "string"}

        with pytest.raises(ValueError, match="cannot be empty"):
            prompt.build(text="", schema=schema)

    def test_build_empty_schema_raises_error(self):
        """Test that empty schema raises ValueError."""
        prompt = NormalizePrompt()

        with pytest.raises(ValueError, match="Schema cannot be empty"):
            prompt.build(text="test", schema={})

    def test_build_none_schema_raises_error(self):
        """Test that None schema raises ValueError."""
        prompt = NormalizePrompt()

        with pytest.raises(ValueError, match="Missing required parameters"):
            prompt.build(text="test", schema=None)

    def test_system_prompt_exists(self):
        """Test that system prompt is defined."""
        prompt = NormalizePrompt()

        system = prompt.system_prompt

        assert system
        assert "JSON" in system
        assert "구조화" in system
