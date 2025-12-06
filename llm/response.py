"""
LLM Response Models

Pydantic models for structured LLM responses with validation and type safety.
"""

from typing import Optional

from pydantic import BaseModel, Field


class LLMUsage(BaseModel):
    """Token usage statistics for an LLM request."""

    prompt_tokens: int = Field(..., description="Number of tokens in the prompt")
    completion_tokens: int = Field(..., description="Number of tokens in the completion")
    total_tokens: int = Field(..., description="Total number of tokens used")


class LLMResponse(BaseModel):
    """
    Unified response model for LLM generation.

    This model is backend-agnostic and represents the essential information
    from any LLM completion request.
    """

    text: str = Field(..., description="Generated text completion")
    usage: LLMUsage = Field(..., description="Token usage statistics")
    model: str = Field(..., description="Model name used for generation")
    finish_reason: str = Field(
        ...,
        description="Reason why generation stopped (stop, length, error, etc.)",
    )
    request_id: Optional[str] = Field(
        None, description="Request ID for tracking and debugging"
    )

    class Config:
        """Pydantic configuration."""

        frozen = False
        validate_assignment = True


class LLMError(Exception):
    """Base exception for LLM client errors."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class LLMConnectionError(LLMError):
    """Raised when unable to connect to LLM server."""

    pass


class LLMTimeoutError(LLMError):
    """Raised when LLM request times out."""

    pass


class LLMValidationError(LLMError):
    """Raised when request parameters are invalid."""

    pass


class LLMServerError(LLMError):
    """Raised when LLM server returns an error."""

    pass
