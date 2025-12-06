"""
Keyword extraction task using LLM.

Extracts key terms, phrases, and concepts from text for indexing and search.
"""

import json
from typing import Any, Dict, List

from ..celery import app
from ..config import settings
from ..utils.retry import InvalidInputError, exponential_backoff, should_retry
from .base import BaseLLMTask


class KeywordsTask(BaseLLMTask):
    """
    Task for extracting keywords from text using LLM.

    Input:
        - text (str): The text to analyze
        - max_keywords (int, optional): Maximum number of keywords (default: 10)
        - language (str, optional): Language of the text (default: "auto")

    Output:
        - keywords (List[str]): List of extracted keywords
        - count (int): Number of keywords extracted
        - categories (Dict[str, List[str]], optional): Keywords grouped by category
    """

    name = "celery_app.tasks.keywords.extract_keywords"
    max_retries = settings.task_max_retries
    default_retry_delay = settings.task_retry_delay

    def build_prompt(self, **kwargs: Any) -> str:
        """
        Build the keyword extraction prompt.

        Args:
            **kwargs: Must contain 'text', optionally 'max_keywords' and 'language'

        Returns:
            str: The formatted prompt

        Raises:
            InvalidInputError: If required inputs are missing or invalid
        """
        # Validate required inputs
        if "text" not in kwargs:
            raise InvalidInputError("Missing required parameter: text")

        text = kwargs["text"]
        if not isinstance(text, str) or not text.strip():
            raise InvalidInputError("Parameter 'text' must be a non-empty string")

        # Get optional parameters
        max_keywords = kwargs.get("max_keywords", 10)
        language = kwargs.get("language", "auto")

        # Validate max_keywords
        if not isinstance(max_keywords, int) or max_keywords < 1:
            raise InvalidInputError("Parameter 'max_keywords' must be an integer >= 1")

        # Build the prompt
        if language == "auto" or language == "en":
            prompt = f"""You are a professional text analysis assistant. Extract the most important keywords and key phrases from the following text.

Requirements:
- Extract up to {max_keywords} keywords/phrases
- Include single words and multi-word phrases
- Focus on main topics, entities, and concepts
- Order by importance (most important first)
- Return ONLY a JSON array of strings, nothing else

Format: ["keyword1", "keyword2", "keyword3", ...]

Text to analyze:
{text}

Keywords (JSON array only):"""
        else:
            # Korean or other languages
            prompt = f"""당신은 전문적인 텍스트 분석 어시스턴트입니다. 다음 텍스트에서 가장 중요한 키워드와 핵심 구문을 추출하세요.

요구사항:
- 최대 {max_keywords}개의 키워드/구문 추출
- 단일 단어와 다중 단어 구문 포함
- 주요 주제, 개체, 개념에 집중
- 중요도 순으로 정렬 (가장 중요한 것 먼저)
- JSON 배열 형식으로만 반환, 다른 내용 없이

형식: ["키워드1", "키워드2", "키워드3", ...]

분석할 텍스트:
{text}

키워드 (JSON 배열만):"""

        return prompt

    def postprocess(self, llm_output: str, **kwargs: Any) -> Dict[str, Any]:
        """
        Postprocess the LLM output into the final result.

        Args:
            llm_output: Raw output from the LLM (expected to be JSON array)
            **kwargs: Original task inputs

        Returns:
            Dict[str, Any]: Processed result with keywords

        Raises:
            InvalidInputError: If LLM output is not valid JSON
        """
        # Clean up the output
        output = llm_output.strip()

        # Try to extract JSON array from output
        try:
            # Try to parse as JSON directly
            keywords = json.loads(output)
        except json.JSONDecodeError:
            # Try to find JSON array in the output
            import re
            match = re.search(r'\[.*\]', output, re.DOTALL)
            if match:
                try:
                    keywords = json.loads(match.group(0))
                except json.JSONDecodeError as e:
                    self.logger.error(
                        "Failed to parse keywords JSON",
                        extra={"output": output, "error": str(e)}
                    )
                    raise InvalidInputError(f"Invalid JSON in LLM output: {e}") from e
            else:
                # Fallback: split by newlines or commas
                self.logger.warning("Could not parse JSON, falling back to text splitting")
                keywords = [
                    line.strip().strip('"-,')
                    for line in output.split('\n')
                    if line.strip() and not line.strip().startswith('#')
                ]
                keywords = [kw for kw in keywords if kw][:kwargs.get("max_keywords", 10)]

        # Validate keywords is a list
        if not isinstance(keywords, list):
            raise InvalidInputError(f"Expected list of keywords, got {type(keywords)}")

        # Filter and clean keywords
        keywords = [
            str(kw).strip()
            for kw in keywords
            if kw and str(kw).strip()
        ]

        # Limit to max_keywords
        max_keywords = kwargs.get("max_keywords", 10)
        keywords = keywords[:max_keywords]

        # Deduplicate while preserving order
        seen = set()
        unique_keywords = []
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower not in seen:
                seen.add(kw_lower)
                unique_keywords.append(kw)

        self.logger.info(
            "Keywords extracted",
            extra={
                "count": len(unique_keywords),
                "requested": max_keywords,
            }
        )

        return {
            "keywords": unique_keywords,
            "count": len(unique_keywords),
        }


@app.task(
    bind=True,
    base=KeywordsTask,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": settings.task_max_retries},
    retry_backoff=True,
    retry_backoff_max=3600,  # Max 1 hour between retries
    retry_jitter=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def extract_keywords(self, **kwargs: Any) -> Dict[str, Any]:
    """
    Celery task wrapper for keyword extraction.

    Args:
        text (str): The text to analyze
        max_keywords (int, optional): Maximum number of keywords (default: 10)
        language (str, optional): Language of the text (default: "auto")

    Returns:
        Dict[str, Any]: Keywords result

    Example:
        >>> result = extract_keywords.delay(
        ...     text="Article about machine learning and AI...",
        ...     max_keywords=5
        ... )
        >>> result.get()
        {
            "keywords": ["machine learning", "AI", "neural networks", "deep learning", "algorithms"],
            "count": 5
        }
    """
    # Check if we should retry based on exception type
    if self.request.retries > 0:
        exc = getattr(self.request, "exception", None)
        if exc and not should_retry(exc):
            self.logger.error(f"Task failed with non-retryable error: {exc}")
            raise exc

    # Calculate retry delay with exponential backoff
    if self.request.retries > 0:
        delay = exponential_backoff(
            retry_count=self.request.retries - 1,
            base_delay=settings.task_retry_delay,
        )
        self.logger.info(f"Retrying after {delay}s...")
        raise self.retry(countdown=delay)

    # Execute the task
    return self.run(**kwargs)
