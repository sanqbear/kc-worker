"""Postprocessor for summarization tasks."""

import re
from typing import Any
from llm.response import LLMResponse
from postprocess.base import Postprocessor


class SummarizePostprocessor(Postprocessor):
    """Postprocessor for extracting and validating summary text.

    This postprocessor extracts the summary from the LLM response,
    performs basic validation, and calculates quality metrics.
    """

    def process(self, response: LLMResponse, **kwargs: Any) -> dict[str, Any]:
        """Process summarization response.

        Args:
            response: The LLM response containing the summary
            **kwargs: Optional parameters:
                - max_length (int): Expected maximum summary length
                - original_length (int): Length of original text for compression ratio

        Returns:
            dict: Processed summary data containing:
                - summary (str): The extracted summary text
                - length (int): Length of summary in characters
                - word_count (int): Number of words in summary
                - compression_ratio (float | None): Ratio of summary/original length
                - confidence (float): Confidence score (0.0-1.0)
                - quality_checks (dict): Results of quality validations

        Raises:
            ValueError: If response is invalid or empty
        """
        self.validate_response(response)

        # Extract parameters
        max_length = kwargs.get("max_length")
        original_length = kwargs.get("original_length")

        # Clean and extract summary
        summary = self._clean_summary(response.content)

        # Calculate metrics
        length = len(summary)
        word_count = len(summary.split())

        # Calculate compression ratio if original length provided
        compression_ratio = None
        if original_length and original_length > 0:
            compression_ratio = length / original_length

        # Perform quality checks
        quality_checks = self._perform_quality_checks(
            summary=summary,
            length=length,
            max_length=max_length,
            response=response
        )

        # Calculate confidence score
        confidence = self.calculate_confidence(response, quality_checks)

        return {
            "summary": summary,
            "length": length,
            "word_count": word_count,
            "compression_ratio": compression_ratio,
            "confidence": confidence,
            "quality_checks": quality_checks,
            "metadata": {
                "model": response.model,
                "finish_reason": response.finish_reason,
                "usage": response.usage,
            }
        }

    def _clean_summary(self, content: str) -> str:
        """Clean and extract summary text from response.

        Args:
            content: Raw response content

        Returns:
            str: Cleaned summary text
        """
        # Remove common prefixes that the LLM might add
        prefixes_to_remove = [
            r'^요약:\s*',
            r'^요약문:\s*',
            r'^summary:\s*',
            r'^결과:\s*',
            r'^\[요약\]\s*',
            r'^【요약】\s*',
        ]

        cleaned = content.strip()
        for prefix in prefixes_to_remove:
            cleaned = re.sub(prefix, '', cleaned, flags=re.IGNORECASE)

        # Remove markdown formatting if present
        cleaned = re.sub(r'^\*\*(.+?)\*\*', r'\1', cleaned)  # Bold
        cleaned = re.sub(r'^#+\s+', '', cleaned)  # Headers

        # Remove extra whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned)
        cleaned = cleaned.strip()

        return cleaned

    def _perform_quality_checks(
        self,
        summary: str,
        length: int,
        max_length: int | None,
        response: LLMResponse
    ) -> dict[str, bool]:
        """Perform quality validation checks on the summary.

        Args:
            summary: The summary text
            length: Length of summary in characters
            max_length: Expected maximum length (optional)
            response: Original LLM response

        Returns:
            dict: Quality check results
        """
        checks = {}

        # Check if summary is not empty
        checks["not_empty"] = len(summary) > 0

        # Check if summary has minimum content (at least 10 characters)
        checks["minimum_length"] = length >= 10

        # Check if summary respects max_length constraint (with 10% tolerance)
        if max_length:
            tolerance = int(max_length * 1.1)
            checks["respects_max_length"] = length <= tolerance
        else:
            checks["respects_max_length"] = True

        # Check if response completed normally
        checks["completed_normally"] = response.finish_reason == "stop"

        # Check if summary doesn't look truncated (no sentence ending mid-word)
        checks["not_truncated"] = not self._looks_truncated(summary)

        # Check if summary contains actual content (not just metadata)
        checks["contains_content"] = self._contains_actual_content(summary)

        return checks

    def _looks_truncated(self, summary: str) -> bool:
        """Check if summary appears to be truncated.

        Args:
            summary: The summary text

        Returns:
            bool: True if summary looks truncated
        """
        if not summary:
            return False

        # Check if it ends with common sentence endings
        sentence_endings = ['.', '!', '?', '다', '요', '음', '함', '됨', '임']
        ends_properly = any(summary.rstrip().endswith(ending) for ending in sentence_endings)

        return not ends_properly

    def _contains_actual_content(self, summary: str) -> bool:
        """Check if summary contains actual content vs just metadata.

        Args:
            summary: The summary text

        Returns:
            bool: True if summary contains real content
        """
        # Check for common metadata phrases that indicate no real summary
        metadata_patterns = [
            r'^(요약|summary|결과)$',
            r'^없음$',
            r'^n/a$',
            r'^해당 없음$',
            r'^정보 없음$',
        ]

        lower_summary = summary.lower().strip()
        for pattern in metadata_patterns:
            if re.match(pattern, lower_summary, re.IGNORECASE):
                return False

        # Check if it has reasonable word count (at least 3 words)
        word_count = len(summary.split())
        return word_count >= 3
