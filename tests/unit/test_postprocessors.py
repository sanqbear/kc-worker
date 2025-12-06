"""Unit tests for postprocessors."""

import pytest
from llm.response import LLMResponse
from postprocess import (
    SummarizePostprocessor,
    KeywordsPostprocessor,
    NormalizePostprocessor
)


class TestSummarizePostprocessor:
    """Test cases for SummarizePostprocessor."""

    def test_process_valid_response(self):
        """Test processing a valid summarization response."""
        response = LLMResponse(
            content="데이터베이스 연결 타임아웃으로 인한 500 에러 발생.",
            model="gpt-4",
            finish_reason="stop",
            usage={"prompt_tokens": 100, "completion_tokens": 30, "total_tokens": 130}
        )

        processor = SummarizePostprocessor()
        result = processor.process(response, max_length=100, original_length=500)

        assert result["summary"] == "데이터베이스 연결 타임아웃으로 인한 500 에러 발생."
        assert result["length"] == len(result["summary"])
        assert result["word_count"] > 0
        assert result["compression_ratio"] is not None
        assert 0.0 <= result["confidence"] <= 1.0
        assert result["quality_checks"]["not_empty"] is True

    def test_clean_summary_removes_prefix(self):
        """Test that summary prefixes are removed."""
        response = LLMResponse(
            content="요약: 이것은 요약문입니다.",
            model="gpt-4",
            finish_reason="stop",
            usage={}
        )

        processor = SummarizePostprocessor()
        result = processor.process(response)

        assert result["summary"] == "이것은 요약문입니다."

    def test_clean_summary_removes_markdown(self):
        """Test that markdown formatting is removed."""
        response = LLMResponse(
            content="**이것은 요약문입니다.**",
            model="gpt-4",
            finish_reason="stop",
            usage={}
        )

        processor = SummarizePostprocessor()
        result = processor.process(response)

        assert "**" not in result["summary"]

    def test_process_empty_response_raises_error(self):
        """Test that empty response raises ValueError."""
        response = LLMResponse(
            content="",
            model="gpt-4",
            finish_reason="stop",
            usage={}
        )

        processor = SummarizePostprocessor()

        with pytest.raises(ValueError, match="Response content is empty"):
            processor.process(response)

    def test_quality_checks_max_length(self):
        """Test that max_length constraint is checked."""
        # Response exceeds max_length
        response = LLMResponse(
            content="이것은 매우 긴 요약문입니다. " * 20,
            model="gpt-4",
            finish_reason="stop",
            usage={}
        )

        processor = SummarizePostprocessor()
        result = processor.process(response, max_length=50)

        assert result["quality_checks"]["respects_max_length"] is False

    def test_quality_checks_truncation(self):
        """Test truncation detection."""
        # Summary that looks truncated
        response = LLMResponse(
            content="이것은 중간에 끊긴 요약",
            model="gpt-4",
            finish_reason="stop",
            usage={}
        )

        processor = SummarizePostprocessor()
        result = processor.process(response)

        assert result["quality_checks"]["not_truncated"] is False


class TestKeywordsPostprocessor:
    """Test cases for KeywordsPostprocessor."""

    def test_process_valid_json(self):
        """Test processing valid JSON keyword array."""
        response = LLMResponse(
            content='["Vue 3", "Pinia", "TypeScript", "Vite"]',
            model="gpt-4",
            finish_reason="stop",
            usage={"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}
        )

        processor = KeywordsPostprocessor()
        result = processor.process(response, max_keywords=10)

        assert result["keywords"] == ["Vue 3", "Pinia", "TypeScript", "Vite"]
        assert result["count"] == 4
        assert result["parsing_info"]["success"] is True
        assert result["parsing_info"]["method"] == "json"
        assert 0.0 <= result["confidence"] <= 1.0

    def test_process_markdown_json(self):
        """Test processing JSON from markdown code block."""
        response = LLMResponse(
            content='```json\n["React", "Redux", "TypeScript"]\n```',
            model="gpt-4",
            finish_reason="stop",
            usage={}
        )

        processor = KeywordsPostprocessor()
        result = processor.process(response)

        assert result["keywords"] == ["React", "Redux", "TypeScript"]
        assert result["parsing_info"]["method"] == "markdown_json"

    def test_process_comma_separated(self):
        """Test processing comma-separated keywords."""
        response = LLMResponse(
            content='키워드: Python, Django, PostgreSQL, Redis',
            model="gpt-4",
            finish_reason="stop",
            usage={}
        )

        processor = KeywordsPostprocessor()
        result = processor.process(response)

        assert "Python" in result["keywords"]
        assert "Django" in result["keywords"]
        assert result["parsing_info"]["method"] == "comma_separated"

    def test_process_line_separated(self):
        """Test processing line-separated keywords."""
        response = LLMResponse(
            content="- Kubernetes\n- Docker\n- Helm",
            model="gpt-4",
            finish_reason="stop",
            usage={}
        )

        processor = KeywordsPostprocessor()
        result = processor.process(response)

        assert "Kubernetes" in result["keywords"]
        assert "Docker" in result["keywords"]
        assert "Helm" in result["keywords"]

    def test_deduplicate_keywords(self):
        """Test keyword deduplication."""
        response = LLMResponse(
            content='["React", "react", "REACT", "TypeScript"]',
            model="gpt-4",
            finish_reason="stop",
            usage={}
        )

        processor = KeywordsPostprocessor()
        result = processor.process(response, deduplicate=True)

        # Should only have one "React" (case-insensitive deduplication)
        react_count = sum(1 for kw in result["keywords"] if kw.lower() == "react")
        assert react_count == 1

    def test_min_keyword_length(self):
        """Test minimum keyword length filtering."""
        response = LLMResponse(
            content='["A", "ab", "abc", "TypeScript"]',
            model="gpt-4",
            finish_reason="stop",
            usage={}
        )

        processor = KeywordsPostprocessor()
        result = processor.process(response, min_keyword_length=3)

        # Only "abc" and "TypeScript" should remain
        assert "A" not in result["keywords"]
        assert "ab" not in result["keywords"]
        assert "abc" in result["keywords"]
        assert "TypeScript" in result["keywords"]

    def test_max_keywords_limit(self):
        """Test that keywords are limited to max_keywords."""
        response = LLMResponse(
            content='["K1", "K2", "K3", "K4", "K5", "K6", "K7", "K8"]',
            model="gpt-4",
            finish_reason="stop",
            usage={}
        )

        processor = KeywordsPostprocessor()
        result = processor.process(response, max_keywords=5)

        assert result["count"] == 5
        assert len(result["keywords"]) == 5

    def test_process_empty_response_raises_error(self):
        """Test that empty response raises ValueError."""
        response = LLMResponse(
            content="",
            model="gpt-4",
            finish_reason="stop",
            usage={}
        )

        processor = KeywordsPostprocessor()

        with pytest.raises(ValueError, match="Response content is empty"):
            processor.process(response)


class TestNormalizePostprocessor:
    """Test cases for NormalizePostprocessor."""

    def test_process_valid_json(self):
        """Test processing valid JSON normalization."""
        schema = {
            "name": "string",
            "email": "string",
            "age": "integer"
        }

        response = LLMResponse(
            content='{"name": "김철수", "email": "kim@example.com", "age": 30}',
            model="gpt-4",
            finish_reason="stop",
            usage={"prompt_tokens": 150, "completion_tokens": 40, "total_tokens": 190}
        )

        processor = NormalizePostprocessor()
        result = processor.process(response, schema=schema)

        assert result["data"]["name"] == "김철수"
        assert result["data"]["email"] == "kim@example.com"
        assert result["data"]["age"] == 30
        assert result["completeness"] == 1.0
        assert result["parsing_info"]["success"] is True
        assert len(result["validation_errors"]) == 0

    def test_process_markdown_json(self):
        """Test processing JSON from markdown code block."""
        schema = {"field": "string"}
        response = LLMResponse(
            content='```json\n{"field": "value"}\n```',
            model="gpt-4",
            finish_reason="stop",
            usage={}
        )

        processor = NormalizePostprocessor()
        result = processor.process(response, schema=schema)

        assert result["data"]["field"] == "value"
        assert result["parsing_info"]["method"] == "markdown_json"

    def test_process_missing_fields(self):
        """Test validation with missing fields."""
        schema = {
            "name": "string",
            "email": "string",
            "phone": "string"
        }

        response = LLMResponse(
            content='{"name": "홍길동", "email": "hong@test.com"}',
            model="gpt-4",
            finish_reason="stop",
            usage={}
        )

        processor = NormalizePostprocessor()
        result = processor.process(response, schema=schema)

        assert len(result["validation_errors"]) > 0
        assert any("Missing" in err for err in result["validation_errors"])
        assert result["completeness"] < 1.0

    def test_process_extra_fields(self):
        """Test validation with extra fields."""
        schema = {"name": "string"}

        response = LLMResponse(
            content='{"name": "김철수", "extra": "value"}',
            model="gpt-4",
            finish_reason="stop",
            usage={}
        )

        processor = NormalizePostprocessor()
        result = processor.process(response, schema=schema, allow_extra_fields=False)

        assert any("Extra fields" in err for err in result["validation_errors"])

    def test_process_allow_extra_fields(self):
        """Test that extra fields are allowed when flag is set."""
        schema = {"name": "string"}

        response = LLMResponse(
            content='{"name": "김철수", "extra": "value"}',
            model="gpt-4",
            finish_reason="stop",
            usage={}
        )

        processor = NormalizePostprocessor()
        result = processor.process(response, schema=schema, allow_extra_fields=True)

        # No error for extra fields
        assert not any("Extra fields" in err for err in result["validation_errors"])

    def test_completeness_calculation(self):
        """Test completeness calculation."""
        schema = {
            "field1": "string",
            "field2": "string",
            "field3": "string",
            "field4": "string"
        }

        # 2 out of 4 fields filled
        response = LLMResponse(
            content='{"field1": "value1", "field2": "value2", "field3": null, "field4": ""}',
            model="gpt-4",
            finish_reason="stop",
            usage={}
        )

        processor = NormalizePostprocessor()
        result = processor.process(response, schema=schema)

        # Only field1 and field2 have meaningful values
        assert result["completeness"] == 0.5

    def test_confidence_score_decreases_with_errors(self):
        """Test that confidence decreases with validation errors."""
        schema = {"name": "string", "age": "integer"}

        # Valid response
        valid_response = LLMResponse(
            content='{"name": "김철수", "age": 30}',
            model="gpt-4",
            finish_reason="stop",
            usage={}
        )

        # Invalid response (missing field)
        invalid_response = LLMResponse(
            content='{"name": "홍길동"}',
            model="gpt-4",
            finish_reason="stop",
            usage={}
        )

        processor = NormalizePostprocessor()
        valid_result = processor.process(valid_response, schema=schema)
        invalid_result = processor.process(invalid_response, schema=schema)

        assert valid_result["confidence"] > invalid_result["confidence"]

    def test_process_no_schema_raises_error(self):
        """Test that missing schema raises ValueError."""
        response = LLMResponse(
            content='{"field": "value"}',
            model="gpt-4",
            finish_reason="stop",
            usage={}
        )

        processor = NormalizePostprocessor()

        with pytest.raises(ValueError, match="Schema is required"):
            processor.process(response)

    def test_process_empty_response_raises_error(self):
        """Test that empty response raises ValueError."""
        response = LLMResponse(
            content="",
            model="gpt-4",
            finish_reason="stop",
            usage={}
        )

        processor = NormalizePostprocessor()

        with pytest.raises(ValueError, match="Response content is empty"):
            processor.process(response, schema={"field": "string"})
