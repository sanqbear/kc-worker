"""Prompt templates for LLM tasks.

This package provides prompt builders for different task types:
- SummarizePrompt: Text summarization
- KeywordsPrompt: Keyword extraction
- NormalizePrompt: JSON normalization from natural language
"""

from llm.prompts.base import PromptTemplate
from llm.prompts.summarize import SummarizePrompt
from llm.prompts.keywords import KeywordsPrompt
from llm.prompts.normalize import NormalizePrompt

__all__ = [
    "PromptTemplate",
    "SummarizePrompt",
    "KeywordsPrompt",
    "NormalizePrompt",
]
