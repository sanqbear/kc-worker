"""Base postprocessor class for LLM responses."""

from abc import ABC, abstractmethod
from typing import Any
from llm.response import LLMResponse


class Postprocessor(ABC):
    """Base class for postprocessors.

    Postprocessors extract structured data from LLM responses and perform
    validation, cleaning, and enrichment of the results.
    """

    @abstractmethod
    def process(self, response: LLMResponse, **kwargs: Any) -> dict[str, Any]:
        """Process LLM response and extract structured data.

        Args:
            response: The LLM response to process
            **kwargs: Task-specific parameters

        Returns:
            dict: Structured data extracted from the response

        Raises:
            ValueError: If the response cannot be processed
        """
        pass

    def validate_response(self, response: LLMResponse) -> None:
        """Validate that the response is valid and non-empty.

        Args:
            response: The LLM response to validate

        Raises:
            ValueError: If the response is invalid or empty
        """
        if response is None:
            raise ValueError("Response cannot be None")

        if not response.content or not response.content.strip():
            raise ValueError("Response content is empty")

    def calculate_confidence(
        self,
        response: LLMResponse,
        quality_indicators: dict[str, bool] | None = None
    ) -> float:
        """Calculate confidence score for the response.

        Args:
            response: The LLM response
            quality_indicators: Dictionary of quality checks (True = pass, False = fail)

        Returns:
            float: Confidence score between 0.0 and 1.0
        """
        # Base confidence from response finish reason
        base_confidence = 1.0 if response.finish_reason == "stop" else 0.5

        # Adjust based on quality indicators
        if quality_indicators:
            passed = sum(1 for v in quality_indicators.values() if v)
            total = len(quality_indicators)
            quality_score = passed / total if total > 0 else 1.0
            return base_confidence * quality_score

        return base_confidence
