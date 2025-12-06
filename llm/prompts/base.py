"""Base prompt template class for LLM tasks."""

from abc import ABC, abstractmethod
from typing import Any


class PromptTemplate(ABC):
    """Base class for prompt templates.

    All prompt templates should inherit from this class and implement
    the build() and system_prompt property methods.
    """

    @abstractmethod
    def build(self, **kwargs: Any) -> str:
        """Build prompt from input data.

        Args:
            **kwargs: Task-specific parameters for building the prompt

        Returns:
            str: The formatted prompt string

        Raises:
            ValueError: If required parameters are missing
        """
        pass

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """System prompt for the task.

        Returns:
            str: The system prompt that defines the AI's role and behavior
        """
        pass

    def validate_params(self, required: list[str], provided: dict[str, Any]) -> None:
        """Validate that all required parameters are provided.

        Args:
            required: List of required parameter names
            provided: Dictionary of provided parameters

        Raises:
            ValueError: If any required parameter is missing
        """
        missing = [param for param in required if param not in provided or provided[param] is None]
        if missing:
            raise ValueError(f"Missing required parameters: {', '.join(missing)}")
