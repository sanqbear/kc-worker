"""Postprocessor for keyword extraction tasks."""

import json
import re
from typing import Any
from llm.response import LLMResponse
from postprocess.base import Postprocessor


class KeywordsPostprocessor(Postprocessor):
    """Postprocessor for parsing and cleaning keyword arrays.

    This postprocessor extracts keywords from LLM responses, handles
    malformed JSON gracefully, and performs deduplication and cleaning.
    """

    def process(self, response: LLMResponse, **kwargs: Any) -> dict[str, Any]:
        """Process keyword extraction response.

        Args:
            response: The LLM response containing keywords
            **kwargs: Optional parameters:
                - max_keywords (int): Expected maximum number of keywords
                - min_keyword_length (int): Minimum length for valid keywords (default: 2)
                - deduplicate (bool): Remove duplicate keywords (default: True)

        Returns:
            dict: Processed keyword data containing:
                - keywords (list[str]): Extracted and cleaned keywords
                - count (int): Number of keywords extracted
                - confidence (float): Confidence score (0.0-1.0)
                - quality_checks (dict): Results of quality validations
                - parsing_info (dict): Information about JSON parsing

        Raises:
            ValueError: If response is invalid or empty
        """
        self.validate_response(response)

        # Extract parameters
        max_keywords = kwargs.get("max_keywords", 10)
        min_keyword_length = kwargs.get("min_keyword_length", 2)
        deduplicate = kwargs.get("deduplicate", True)

        # Parse keywords from response
        keywords, parsing_info = self._parse_keywords(response.content)

        # Clean and validate keywords
        keywords = self._clean_keywords(
            keywords=keywords,
            min_length=min_keyword_length,
            deduplicate=deduplicate
        )

        # Limit to max_keywords
        if len(keywords) > max_keywords:
            keywords = keywords[:max_keywords]

        # Perform quality checks
        quality_checks = self._perform_quality_checks(
            keywords=keywords,
            max_keywords=max_keywords,
            response=response,
            parsing_successful=parsing_info["success"]
        )

        # Calculate confidence score
        confidence = self.calculate_confidence(response, quality_checks)

        return {
            "keywords": keywords,
            "count": len(keywords),
            "confidence": confidence,
            "quality_checks": quality_checks,
            "parsing_info": parsing_info,
            "metadata": {
                "model": response.model,
                "finish_reason": response.finish_reason,
                "usage": response.usage,
            }
        }

    def _parse_keywords(self, content: str) -> tuple[list[str], dict[str, Any]]:
        """Parse keywords from response content.

        Attempts multiple parsing strategies:
        1. Standard JSON array parsing
        2. Extract JSON from markdown code blocks
        3. Fallback to comma-separated or line-separated parsing

        Args:
            content: Raw response content

        Returns:
            tuple: (keywords list, parsing info dict)
        """
        parsing_info = {
            "success": False,
            "method": None,
            "error": None
        }

        cleaned_content = content.strip()

        # Strategy 1: Direct JSON parsing
        try:
            keywords = json.loads(cleaned_content)
            if isinstance(keywords, list):
                parsing_info["success"] = True
                parsing_info["method"] = "json"
                return keywords, parsing_info
        except json.JSONDecodeError:
            pass

        # Strategy 2: Extract from markdown code block
        json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', cleaned_content, re.DOTALL)
        if json_match:
            try:
                keywords = json.loads(json_match.group(1))
                if isinstance(keywords, list):
                    parsing_info["success"] = True
                    parsing_info["method"] = "markdown_json"
                    return keywords, parsing_info
            except json.JSONDecodeError:
                pass

        # Strategy 3: Find JSON array pattern in text
        array_match = re.search(r'\[([^\]]+)\]', cleaned_content)
        if array_match:
            try:
                keywords = json.loads('[' + array_match.group(1) + ']')
                if isinstance(keywords, list):
                    parsing_info["success"] = True
                    parsing_info["method"] = "pattern_match"
                    return keywords, parsing_info
            except json.JSONDecodeError:
                pass

        # Strategy 4: Fallback to comma-separated
        if ',' in cleaned_content:
            # Remove common prefixes
            cleaned_content = re.sub(r'^(키워드|keywords?):\s*', '', cleaned_content, flags=re.IGNORECASE)
            # Remove brackets if present
            cleaned_content = re.sub(r'[\[\]]', '', cleaned_content)
            # Split by comma
            keywords = [kw.strip().strip('"\'') for kw in cleaned_content.split(',')]
            keywords = [kw for kw in keywords if kw]

            if keywords:
                parsing_info["success"] = True
                parsing_info["method"] = "comma_separated"
                return keywords, parsing_info

        # Strategy 5: Line-separated fallback
        lines = cleaned_content.split('\n')
        keywords = []
        for line in lines:
            line = line.strip()
            # Remove bullet points, numbers, quotes
            line = re.sub(r'^[\-\*\d\.]+\s*', '', line)
            line = line.strip('"\'')
            if line and len(line) > 1:
                keywords.append(line)

        if keywords:
            parsing_info["success"] = True
            parsing_info["method"] = "line_separated"
            return keywords, parsing_info

        # Parsing failed
        parsing_info["success"] = False
        parsing_info["method"] = None
        parsing_info["error"] = "Could not parse keywords from response"

        return [], parsing_info

    def _clean_keywords(
        self,
        keywords: list[str],
        min_length: int,
        deduplicate: bool
    ) -> list[str]:
        """Clean and validate keyword list.

        Args:
            keywords: Raw keyword list
            min_length: Minimum keyword length
            deduplicate: Whether to remove duplicates

        Returns:
            list[str]: Cleaned keyword list
        """
        cleaned = []
        seen = set()

        for keyword in keywords:
            # Convert to string if not already
            if not isinstance(keyword, str):
                keyword = str(keyword)

            # Basic cleaning
            keyword = keyword.strip()
            keyword = keyword.strip('"\'')  # Remove quotes
            keyword = keyword.strip('.,;:!?')  # Remove punctuation
            keyword = re.sub(r'\s+', ' ', keyword)  # Normalize whitespace

            # Skip if too short
            if len(keyword) < min_length:
                continue

            # Skip if looks like metadata
            if self._is_metadata(keyword):
                continue

            # Deduplication (case-insensitive)
            if deduplicate:
                keyword_lower = keyword.lower()
                if keyword_lower in seen:
                    continue
                seen.add(keyword_lower)

            cleaned.append(keyword)

        return cleaned

    def _is_metadata(self, keyword: str) -> bool:
        """Check if keyword looks like metadata rather than actual keyword.

        Args:
            keyword: The keyword to check

        Returns:
            bool: True if keyword appears to be metadata
        """
        metadata_patterns = [
            r'^키워드\d*$',
            r'^keyword\d*$',
            r'^tag\d*$',
            r'^없음$',
            r'^n/a$',
            r'^해당사항\s*없음$',
        ]

        keyword_lower = keyword.lower()
        for pattern in metadata_patterns:
            if re.match(pattern, keyword_lower, re.IGNORECASE):
                return True

        return False

    def _perform_quality_checks(
        self,
        keywords: list[str],
        max_keywords: int,
        response: LLMResponse,
        parsing_successful: bool
    ) -> dict[str, bool]:
        """Perform quality validation checks on keywords.

        Args:
            keywords: Extracted keywords
            max_keywords: Expected maximum count
            response: Original LLM response
            parsing_successful: Whether JSON parsing succeeded

        Returns:
            dict: Quality check results
        """
        checks = {}

        # Check if parsing succeeded
        checks["parsing_succeeded"] = parsing_successful

        # Check if keywords were extracted
        checks["keywords_found"] = len(keywords) > 0

        # Check if keyword count is reasonable (at least 1, at most max_keywords)
        checks["reasonable_count"] = 1 <= len(keywords) <= max_keywords

        # Check if response completed normally
        checks["completed_normally"] = response.finish_reason == "stop"

        # Check if keywords are diverse (not all identical)
        if keywords:
            unique_ratio = len(set(kw.lower() for kw in keywords)) / len(keywords)
            checks["diverse_keywords"] = unique_ratio > 0.5
        else:
            checks["diverse_keywords"] = False

        # Check average keyword quality (length and complexity)
        if keywords:
            avg_length = sum(len(kw) for kw in keywords) / len(keywords)
            checks["quality_keywords"] = avg_length >= 3  # At least 3 chars average
        else:
            checks["quality_keywords"] = False

        return checks
