"""Prompt template for JSON normalization from natural language."""

import json
from typing import Any
from llm.prompts.base import PromptTemplate


class NormalizePrompt(PromptTemplate):
    """Prompt template for converting natural language to structured JSON.

    This prompt instructs the LLM to extract structured information from
    unstructured text and format it according to a provided schema.
    """

    @property
    def system_prompt(self) -> str:
        """System prompt defining the JSON normalization task."""
        return """당신은 자연어 텍스트를 구조화된 JSON 데이터로 변환하는 전문 AI입니다.

주어진 텍스트에서 정보를 추출하여 지정된 JSON 스키마에 맞게 변환하는 것이 당신의 임무입니다.

정보 추출 및 변환 원칙:
1. 원문에 명시된 정보만 추출 (추측하거나 추가 정보 생성 금지)
2. 스키마의 모든 필드를 채우되, 정보가 없는 경우 null 사용
3. 데이터 타입을 정확히 준수 (문자열, 숫자, 불리언, 배열, 객체 등)
4. 날짜/시간은 ISO 8601 형식 사용 (예: 2024-01-15T09:30:00Z)
5. 열거형(enum) 필드는 지정된 값만 사용
6. 배열 필드는 관련 정보를 모두 포함

출력 형식:
- 반드시 유효한 JSON 객체만 출력
- JSON 이외의 설명, 주석, 메타 정보는 포함하지 않음
- 올바른 JSON 문법 준수 (따옴표, 쉼표, 중괄호 등)"""

    def build(self, text: str, schema: dict[str, Any], **kwargs: Any) -> str:
        """Build JSON normalization prompt.

        Args:
            text: The natural language text to normalize
            schema: JSON schema defining the expected structure
            **kwargs: Additional parameters (ignored)

        Returns:
            str: The formatted prompt

        Raises:
            ValueError: If text or schema is empty/None
        """
        self.validate_params(["text", "schema"], {"text": text, "schema": schema})

        if not text.strip():
            raise ValueError("Text to normalize cannot be empty")

        if not schema:
            raise ValueError("Schema cannot be empty")

        # Format schema for readability
        schema_str = json.dumps(schema, ensure_ascii=False, indent=2)

        # Build the user prompt
        prompt = f"""다음 텍스트의 정보를 주어진 JSON 스키마에 맞게 구조화해주세요:

--- 텍스트 시작 ---
{text.strip()}
--- 텍스트 끝 ---

--- JSON 스키마 ---
{schema_str}
--- 스키마 끝 ---

위 텍스트에서 정보를 추출하여 스키마에 맞는 JSON 객체를 생성해주세요."""

        return prompt

    def build_with_examples(
        self,
        text: str,
        schema: dict[str, Any],
        examples: list[dict[str, Any]] | None = None,
        **kwargs: Any
    ) -> str:
        """Build JSON normalization prompt with examples.

        Args:
            text: The natural language text to normalize
            schema: JSON schema defining the expected structure
            examples: List of example input-output pairs (optional)
            **kwargs: Additional parameters (ignored)

        Returns:
            str: The formatted prompt
        """
        self.validate_params(["text", "schema"], {"text": text, "schema": schema})

        if not text.strip():
            raise ValueError("Text to normalize cannot be empty")

        if not schema:
            raise ValueError("Schema cannot be empty")

        # Format schema
        schema_str = json.dumps(schema, ensure_ascii=False, indent=2)

        # Build examples section
        examples_section = ""
        if examples:
            examples_list = []
            for idx, example in enumerate(examples, 1):
                example_input = example.get("input", "")
                example_output = json.dumps(
                    example.get("output", {}),
                    ensure_ascii=False,
                    indent=2
                )
                examples_list.append(f"""예시 {idx}:
입력: {example_input}
출력:
{example_output}""")

            examples_section = "\n\n--- 변환 예시 ---\n" + "\n\n".join(examples_list) + "\n--- 예시 끝 ---"

        # Build the user prompt
        prompt = f"""다음 텍스트의 정보를 주어진 JSON 스키마에 맞게 구조화해주세요:

--- JSON 스키마 ---
{schema_str}
--- 스키마 끝 ---{examples_section}

--- 변환할 텍스트 ---
{text.strip()}
--- 텍스트 끝 ---

위 텍스트에서 정보를 추출하여 스키마에 맞는 JSON 객체를 생성해주세요."""

        return prompt

    def build_with_field_descriptions(
        self,
        text: str,
        schema: dict[str, Any],
        field_descriptions: dict[str, str] | None = None,
        **kwargs: Any
    ) -> str:
        """Build JSON normalization prompt with detailed field descriptions.

        Args:
            text: The natural language text to normalize
            schema: JSON schema defining the expected structure
            field_descriptions: Dictionary mapping field names to descriptions
            **kwargs: Additional parameters (ignored)

        Returns:
            str: The formatted prompt
        """
        self.validate_params(["text", "schema"], {"text": text, "schema": schema})

        if not text.strip():
            raise ValueError("Text to normalize cannot be empty")

        if not schema:
            raise ValueError("Schema cannot be empty")

        # Format schema
        schema_str = json.dumps(schema, ensure_ascii=False, indent=2)

        # Build field descriptions section
        descriptions_section = ""
        if field_descriptions:
            desc_list = [f"- {field}: {desc}" for field, desc in field_descriptions.items()]
            descriptions_section = "\n\n--- 필드 설명 ---\n" + "\n".join(desc_list) + "\n--- 설명 끝 ---"

        # Build the user prompt
        prompt = f"""다음 텍스트의 정보를 주어진 JSON 스키마에 맞게 구조화해주세요:

--- JSON 스키마 ---
{schema_str}
--- 스키마 끝 ---{descriptions_section}

--- 변환할 텍스트 ---
{text.strip()}
--- 텍스트 끝 ---

위 텍스트에서 정보를 추출하여 스키마에 맞는 JSON 객체를 생성해주세요."""

        return prompt
