"""
Task definitions for the Celery worker service.

Available tasks:
- summarize_text: Generate concise summaries from text
- extract_keywords: Extract key terms from text
- normalize_json: Convert natural language to structured JSON
"""

from .summarize import summarize_text
from .keywords import extract_keywords
from .normalize import normalize_json

__all__ = [
    "summarize_text",
    "extract_keywords",
    "normalize_json",
]
