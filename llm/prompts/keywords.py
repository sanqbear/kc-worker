"""Prompt template for keyword extraction."""

from typing import Any
from llm.prompts.base import PromptTemplate


class KeywordsPrompt(PromptTemplate):
    """Prompt template for extracting keywords in Korean.

    This prompt instructs the LLM to identify and extract the most relevant
    keywords from the given text, returning them as a JSON array.
    """

    @property
    def system_prompt(self) -> str:
        """System prompt defining the keyword extraction task."""
        return """당신은 텍스트에서 핵심 키워드를 추출하는 전문 AI입니다.

주어진 텍스트에서 가장 중요하고 의미있는 키워드를 식별하는 것이 당신의 임무입니다.

키워드 추출 원칙:
1. 텍스트의 주제와 핵심 내용을 대표하는 단어 선택
2. 구체적이고 의미있는 용어 우선 (일반적인 단어보다는 전문 용어, 고유명사 등)
3. 검색 및 분류에 유용한 키워드 추출
4. 중복되거나 유사한 의미의 키워드는 제외
5. 단일 단어 또는 2-3단어로 구성된 짧은 구문
6. 원문에 실제로 등장하거나 직접적으로 관련된 키워드만 추출

출력 형식:
- 반드시 JSON 배열 형식으로 출력: ["키워드1", "키워드2", "키워드3"]
- 다른 설명이나 메타 정보 없이 JSON 배열만 출력
- 키워드는 중요도 순으로 정렬"""

    def build(self, text: str, max_keywords: int = 10, **kwargs: Any) -> str:
        """Build keyword extraction prompt.

        Args:
            text: The text to extract keywords from
            max_keywords: Maximum number of keywords to extract (default: 10)
            **kwargs: Additional parameters (ignored)

        Returns:
            str: The formatted prompt

        Raises:
            ValueError: If text is empty or None, or max_keywords is invalid
        """
        self.validate_params(["text"], {"text": text})

        if not text.strip():
            raise ValueError("Text for keyword extraction cannot be empty")

        if max_keywords < 1:
            raise ValueError("max_keywords must be at least 1")

        # Build the user prompt
        prompt = f"""다음 텍스트에서 핵심 키워드를 {max_keywords}개 이하로 추출해주세요:

--- 텍스트 시작 ---
{text.strip()}
--- 텍스트 끝 ---

위 텍스트의 핵심 키워드를 JSON 배열 형식으로 출력해주세요.
형식: ["키워드1", "키워드2", "키워드3"]"""

        return prompt

    def build_with_domain(
        self,
        text: str,
        max_keywords: int = 10,
        domain: str | None = None,
        **kwargs: Any
    ) -> str:
        """Build keyword extraction prompt with domain context.

        Args:
            text: The text to extract keywords from
            max_keywords: Maximum number of keywords to extract
            domain: Domain or category context (e.g., "기술 문서", "고객 지원")
            **kwargs: Additional parameters (ignored)

        Returns:
            str: The formatted prompt
        """
        self.validate_params(["text"], {"text": text})

        if not text.strip():
            raise ValueError("Text for keyword extraction cannot be empty")

        if max_keywords < 1:
            raise ValueError("max_keywords must be at least 1")

        # Build domain context
        domain_context = ""
        if domain:
            domain_context = f"\n\n문서 분야: {domain}\n해당 분야에 특화된 전문 용어와 관련 키워드를 우선적으로 추출하세요."

        # Build the user prompt
        prompt = f"""다음 텍스트에서 핵심 키워드를 {max_keywords}개 이하로 추출해주세요:{domain_context}

--- 텍스트 시작 ---
{text.strip()}
--- 텍스트 끝 ---

위 텍스트의 핵심 키워드를 JSON 배열 형식으로 출력해주세요.
형식: ["키워드1", "키워드2", "키워드3"]"""

        return prompt

    def build_multilingual(
        self,
        text: str,
        max_keywords: int = 10,
        include_english: bool = False,
        **kwargs: Any
    ) -> str:
        """Build keyword extraction prompt with multilingual support.

        Args:
            text: The text to extract keywords from
            max_keywords: Maximum number of keywords to extract
            include_english: If True, include English keywords alongside Korean
            **kwargs: Additional parameters (ignored)

        Returns:
            str: The formatted prompt
        """
        self.validate_params(["text"], {"text": text})

        if not text.strip():
            raise ValueError("Text for keyword extraction cannot be empty")

        if max_keywords < 1:
            raise ValueError("max_keywords must be at least 1")

        # Build language instruction
        lang_instruction = ""
        if include_english:
            lang_instruction = "\n\n언어: 한국어와 영어 키워드를 모두 포함할 수 있습니다. 원문에서 사용된 언어를 그대로 사용하세요."

        # Build the user prompt
        prompt = f"""다음 텍스트에서 핵심 키워드를 {max_keywords}개 이하로 추출해주세요:{lang_instruction}

--- 텍스트 시작 ---
{text.strip()}
--- 텍스트 끝 ---

위 텍스트의 핵심 키워드를 JSON 배열 형식으로 출력해주세요.
형식: ["키워드1", "키워드2", "키워드3"]"""

        return prompt
