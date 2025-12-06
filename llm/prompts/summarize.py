"""Prompt template for text summarization."""

from typing import Any
from llm.prompts.base import PromptTemplate


class SummarizePrompt(PromptTemplate):
    """Prompt template for summarizing text in Korean.

    This prompt instructs the LLM to create concise, informative summaries
    while preserving key information and context.
    """

    @property
    def system_prompt(self) -> str:
        """System prompt defining the summarization task."""
        return """당신은 전문적인 요약 작성 AI입니다.

주어진 텍스트를 명확하고 간결하게 요약하는 것이 당신의 임무입니다.

요약 작성 원칙:
1. 핵심 정보와 주요 내용을 빠짐없이 포함
2. 원문의 의미와 맥락을 정확히 보존
3. 불필요한 세부사항은 생략하되 중요한 세부사항은 유지
4. 명확하고 이해하기 쉬운 한국어 사용
5. 지정된 길이 제한을 준수
6. 원문에 없는 내용을 추가하거나 해석하지 않음

요약문만 출력하고, 추가 설명이나 메타 정보는 포함하지 마세요."""

    def build(self, text: str, max_length: int | None = None, **kwargs: Any) -> str:
        """Build summarization prompt.

        Args:
            text: The text to summarize
            max_length: Maximum length of the summary in characters (optional)
            **kwargs: Additional parameters (ignored)

        Returns:
            str: The formatted prompt

        Raises:
            ValueError: If text is empty or None
        """
        self.validate_params(["text"], {"text": text})

        if not text.strip():
            raise ValueError("Text to summarize cannot be empty")

        # Build length constraint
        length_constraint = ""
        if max_length and max_length > 0:
            length_constraint = f"\n\n요약 길이 제한: 최대 {max_length:,}자"

        # Build the user prompt
        prompt = f"""다음 텍스트를 요약해주세요:{length_constraint}

--- 원문 시작 ---
{text.strip()}
--- 원문 끝 ---

위 텍스트의 핵심 내용을 담은 요약문을 작성해주세요."""

        return prompt

    def build_with_context(
        self,
        text: str,
        max_length: int | None = None,
        context: str | None = None,
        **kwargs: Any
    ) -> str:
        """Build summarization prompt with additional context.

        Args:
            text: The text to summarize
            max_length: Maximum length of the summary in characters
            context: Additional context about the text (e.g., "티켓 내용", "회의록")
            **kwargs: Additional parameters (ignored)

        Returns:
            str: The formatted prompt
        """
        self.validate_params(["text"], {"text": text})

        if not text.strip():
            raise ValueError("Text to summarize cannot be empty")

        # Build length constraint
        length_constraint = ""
        if max_length and max_length > 0:
            length_constraint = f"\n\n요약 길이 제한: 최대 {max_length:,}자"

        # Build context information
        context_info = ""
        if context:
            context_info = f"\n\n문서 유형: {context}"

        # Build the user prompt
        prompt = f"""다음 텍스트를 요약해주세요:{length_constraint}{context_info}

--- 원문 시작 ---
{text.strip()}
--- 원문 끝 ---

위 텍스트의 핵심 내용을 담은 요약문을 작성해주세요."""

        return prompt
