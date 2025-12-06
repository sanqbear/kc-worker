"""
Text summarization task using LLM.

Generates concise summaries from longer text inputs while preserving key information.
"""

from typing import Any, Dict

from ..celery import app
from ..config import settings
from ..utils.retry import InvalidInputError, exponential_backoff, should_retry
from .base import BaseLLMTask


class SummarizeTask(BaseLLMTask):
    """
    Task for generating text summaries using LLM.

    Input:
        - text (str): The text to summarize
        - max_length (int, optional): Maximum summary length in words (default: 200)
        - language (str, optional): Language of the text (default: "auto")

    Output:
        - summary (str): The generated summary
        - original_length (int): Word count of original text
        - summary_length (int): Word count of summary
        - compression_ratio (float): summary_length / original_length
    """

    name = "celery_app.tasks.summarize.summarize_text"
    max_retries = settings.task_max_retries
    default_retry_delay = settings.task_retry_delay

    def build_prompt(self, **kwargs: Any) -> str:
        """
        Build the summarization prompt.

        Args:
            **kwargs: Must contain 'text', optionally 'max_length' and 'language'

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
        max_length = kwargs.get("max_length", 200)
        language = kwargs.get("language", "auto")

        # Validate max_length
        if not isinstance(max_length, int) or max_length < 10:
            raise InvalidInputError("Parameter 'max_length' must be an integer >= 10")

        # Build the prompt
        if language == "auto" or language == "en":
            prompt = f"""You are a professional summarization assistant. Your task is to create a concise summary of the following text.

Requirements:
- Maximum length: {max_length} words
- Preserve key information and main ideas
- Use clear, professional language
- Do not add information not present in the original text

Text to summarize:
{text}

Summary:"""
        else:
            # Korean or other languages
            prompt = f"""당신은 전문적인 요약 어시스턴트입니다. 다음 텍스트의 간결한 요약을 작성하세요.

요구사항:
- 최대 길이: {max_length} 단어
- 핵심 정보와 주요 아이디어 보존
- 명확하고 전문적인 언어 사용
- 원문에 없는 정보 추가 금지

요약할 텍스트:
{text}

요약:"""

        return prompt

    def postprocess(self, llm_output: str, **kwargs: Any) -> Dict[str, Any]:
        """
        Postprocess the LLM output into the final result.

        Args:
            llm_output: Raw output from the LLM
            **kwargs: Original task inputs

        Returns:
            Dict[str, Any]: Processed result with metadata
        """
        # Clean up the summary
        summary = llm_output.strip()

        # Calculate metrics
        original_text = kwargs["text"]
        original_length = len(original_text.split())
        summary_length = len(summary.split())

        compression_ratio = summary_length / original_length if original_length > 0 else 0.0

        self.logger.info(
            "Summary generated",
            extra={
                "original_length": original_length,
                "summary_length": summary_length,
                "compression_ratio": f"{compression_ratio:.2%}",
            }
        )

        return {
            "summary": summary,
            "original_length": original_length,
            "summary_length": summary_length,
            "compression_ratio": round(compression_ratio, 4),
        }


@app.task(
    bind=True,
    base=SummarizeTask,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": settings.task_max_retries},
    retry_backoff=True,
    retry_backoff_max=3600,  # Max 1 hour between retries
    retry_jitter=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def summarize_text(self, **kwargs: Any) -> Dict[str, Any]:
    """
    Celery task wrapper for text summarization.

    Args:
        text (str): The text to summarize
        max_length (int, optional): Maximum summary length in words (default: 200)
        language (str, optional): Language of the text (default: "auto")

    Returns:
        Dict[str, Any]: Summary result with metadata

    Example:
        >>> result = summarize_text.delay(
        ...     text="Long article text here...",
        ...     max_length=150
        ... )
        >>> result.get()
        {
            "summary": "Concise summary here...",
            "original_length": 500,
            "summary_length": 145,
            "compression_ratio": 0.29
        }
    """
    # Check if we should retry based on exception type
    if self.request.retries > 0:
        # Get the exception from the request context
        exc = getattr(self.request, "exception", None)
        if exc and not should_retry(exc):
            # Don't retry non-retryable errors
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
