"""Postprocessor for JSON normalization tasks."""

import json
import re
from typing import Any
from llm.response import LLMResponse
from postprocess.base import Postprocessor


class NormalizePostprocessor(Postprocessor):
    """Postprocessor for validating and scoring JSON normalization.

    This postprocessor extracts JSON from LLM responses, validates it
    against the provided schema, and calculates a confidence score based
    on field completeness and data quality.
    """

    def process(self, response: LLMResponse, **kwargs: Any) -> dict[str, Any]:
        """Process JSON normalization response.

        Args:
            response: The LLM response containing JSON data
            **kwargs: Required parameters:
                - schema (dict): The expected JSON schema
                Optional parameters:
                - strict_validation (bool): Enforce strict type checking (default: True)
                - allow_extra_fields (bool): Allow fields not in schema (default: False)

        Returns:
            dict: Processed normalization data containing:
                - data (dict): Extracted and validated JSON data
                - confidence (float): Confidence score (0.0-1.0)
                - completeness (float): Field completeness ratio (0.0-1.0)
                - quality_checks (dict): Results of quality validations
                - validation_errors (list[str]): List of validation errors
                - parsing_info (dict): Information about JSON parsing

        Raises:
            ValueError: If response is invalid, empty, or schema is missing
        """
        self.validate_response(response)

        # Extract required schema parameter
        schema = kwargs.get("schema")
        if not schema:
            raise ValueError("Schema is required for normalization postprocessing")

        # Extract optional parameters
        strict_validation = kwargs.get("strict_validation", True)
        allow_extra_fields = kwargs.get("allow_extra_fields", False)

        # Parse JSON from response
        data, parsing_info = self._parse_json(response.content)

        # Validate against schema
        validation_errors = self._validate_schema(
            data=data,
            schema=schema,
            strict=strict_validation,
            allow_extra=allow_extra_fields
        )

        # Calculate completeness and quality metrics
        completeness = self._calculate_completeness(data, schema)
        quality_metrics = self._calculate_quality_metrics(data, schema)

        # Perform quality checks
        quality_checks = self._perform_quality_checks(
            data=data,
            response=response,
            parsing_successful=parsing_info["success"],
            has_validation_errors=len(validation_errors) > 0,
            completeness=completeness
        )

        # Calculate confidence score
        confidence = self._calculate_confidence_score(
            response=response,
            quality_checks=quality_checks,
            completeness=completeness,
            validation_errors=validation_errors
        )

        return {
            "data": data,
            "confidence": confidence,
            "completeness": completeness,
            "quality_metrics": quality_metrics,
            "quality_checks": quality_checks,
            "validation_errors": validation_errors,
            "parsing_info": parsing_info,
            "metadata": {
                "model": response.model,
                "finish_reason": response.finish_reason,
                "usage": response.usage,
            }
        }

    def _parse_json(self, content: str) -> tuple[dict[str, Any], dict[str, Any]]:
        """Parse JSON from response content.

        Attempts multiple parsing strategies:
        1. Standard JSON parsing
        2. Extract JSON from markdown code blocks
        3. Find JSON object pattern in text

        Args:
            content: Raw response content

        Returns:
            tuple: (parsed data dict, parsing info dict)
        """
        parsing_info = {
            "success": False,
            "method": None,
            "error": None
        }

        cleaned_content = content.strip()

        # Strategy 1: Direct JSON parsing
        try:
            data = json.loads(cleaned_content)
            if isinstance(data, dict):
                parsing_info["success"] = True
                parsing_info["method"] = "json"
                return data, parsing_info
        except json.JSONDecodeError as e:
            parsing_info["error"] = str(e)

        # Strategy 2: Extract from markdown code block
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', cleaned_content, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                if isinstance(data, dict):
                    parsing_info["success"] = True
                    parsing_info["method"] = "markdown_json"
                    return data, parsing_info
            except json.JSONDecodeError:
                pass

        # Strategy 3: Find JSON object pattern in text
        object_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', cleaned_content, re.DOTALL)
        if object_match:
            try:
                data = json.loads(object_match.group(0))
                if isinstance(data, dict):
                    parsing_info["success"] = True
                    parsing_info["method"] = "pattern_match"
                    return data, parsing_info
            except json.JSONDecodeError:
                pass

        # Parsing failed - return empty dict
        parsing_info["success"] = False
        parsing_info["method"] = None
        if not parsing_info["error"]:
            parsing_info["error"] = "Could not parse JSON from response"

        return {}, parsing_info

    def _validate_schema(
        self,
        data: dict[str, Any],
        schema: dict[str, Any],
        strict: bool,
        allow_extra: bool
    ) -> list[str]:
        """Validate data against schema.

        Args:
            data: Parsed JSON data
            schema: Expected schema
            strict: Enforce strict type checking
            allow_extra: Allow extra fields not in schema

        Returns:
            list[str]: List of validation error messages
        """
        errors = []

        if not data:
            errors.append("Parsed data is empty")
            return errors

        # Check for missing required fields
        schema_fields = set(schema.keys()) if isinstance(schema, dict) else set()
        data_fields = set(data.keys())

        missing_fields = schema_fields - data_fields
        if missing_fields:
            errors.append(f"Missing required fields: {', '.join(sorted(missing_fields))}")

        # Check for extra fields
        if not allow_extra:
            extra_fields = data_fields - schema_fields
            if extra_fields:
                errors.append(f"Extra fields not in schema: {', '.join(sorted(extra_fields))}")

        # Validate field types if strict mode
        if strict and isinstance(schema, dict):
            for field, expected_type in schema.items():
                if field in data:
                    actual_value = data[field]
                    if not self._validate_type(actual_value, expected_type):
                        errors.append(
                            f"Field '{field}' has incorrect type. "
                            f"Expected: {expected_type}, Got: {type(actual_value).__name__}"
                        )

        return errors

    def _validate_type(self, value: Any, expected_type: Any) -> bool:
        """Validate value type against expected type.

        Args:
            value: The value to check
            expected_type: Expected type (can be type object or string)

        Returns:
            bool: True if type matches
        """
        if value is None:
            return True  # Allow null for any type

        # Handle string type specifications
        if isinstance(expected_type, str):
            type_map = {
                "string": str,
                "number": (int, float),
                "integer": int,
                "float": float,
                "boolean": bool,
                "array": list,
                "object": dict,
            }
            expected_type = type_map.get(expected_type.lower(), str)

        return isinstance(value, expected_type)

    def _calculate_completeness(self, data: dict[str, Any], schema: dict[str, Any]) -> float:
        """Calculate field completeness ratio.

        Args:
            data: Parsed JSON data
            schema: Expected schema

        Returns:
            float: Completeness ratio (0.0-1.0)
        """
        if not schema or not isinstance(schema, dict):
            return 1.0

        if not data:
            return 0.0

        total_fields = len(schema)
        filled_fields = 0

        for field in schema.keys():
            if field in data and data[field] is not None:
                # Check if the value is meaningful (not empty string, empty list, etc.)
                value = data[field]
                if isinstance(value, str) and value.strip():
                    filled_fields += 1
                elif isinstance(value, (list, dict)) and len(value) > 0:
                    filled_fields += 1
                elif isinstance(value, (int, float, bool)):
                    filled_fields += 1

        return filled_fields / total_fields if total_fields > 0 else 1.0

    def _calculate_quality_metrics(
        self,
        data: dict[str, Any],
        schema: dict[str, Any]
    ) -> dict[str, Any]:
        """Calculate quality metrics for the normalized data.

        Args:
            data: Parsed JSON data
            schema: Expected schema

        Returns:
            dict: Quality metrics
        """
        metrics = {
            "total_fields": len(schema) if isinstance(schema, dict) else 0,
            "filled_fields": 0,
            "null_fields": 0,
            "empty_fields": 0,
            "field_coverage": 0.0,
        }

        if not data or not isinstance(schema, dict):
            return metrics

        for field in schema.keys():
            if field not in data:
                metrics["null_fields"] += 1
            elif data[field] is None:
                metrics["null_fields"] += 1
            elif isinstance(data[field], str) and not data[field].strip():
                metrics["empty_fields"] += 1
            elif isinstance(data[field], (list, dict)) and len(data[field]) == 0:
                metrics["empty_fields"] += 1
            else:
                metrics["filled_fields"] += 1

        # Calculate field coverage
        if metrics["total_fields"] > 0:
            metrics["field_coverage"] = metrics["filled_fields"] / metrics["total_fields"]

        return metrics

    def _perform_quality_checks(
        self,
        data: dict[str, Any],
        response: LLMResponse,
        parsing_successful: bool,
        has_validation_errors: bool,
        completeness: float
    ) -> dict[str, bool]:
        """Perform quality validation checks on normalized data.

        Args:
            data: Parsed JSON data
            response: Original LLM response
            parsing_successful: Whether JSON parsing succeeded
            has_validation_errors: Whether schema validation failed
            completeness: Field completeness ratio

        Returns:
            dict: Quality check results
        """
        checks = {}

        # Check if parsing succeeded
        checks["parsing_succeeded"] = parsing_successful

        # Check if data was extracted
        checks["data_found"] = len(data) > 0

        # Check if validation passed
        checks["schema_valid"] = not has_validation_errors

        # Check if response completed normally
        checks["completed_normally"] = response.finish_reason == "stop"

        # Check if completeness is acceptable (at least 50%)
        checks["acceptable_completeness"] = completeness >= 0.5

        # Check if completeness is high quality (at least 80%)
        checks["high_completeness"] = completeness >= 0.8

        return checks

    def _calculate_confidence_score(
        self,
        response: LLMResponse,
        quality_checks: dict[str, bool],
        completeness: float,
        validation_errors: list[str]
    ) -> float:
        """Calculate overall confidence score.

        Args:
            response: Original LLM response
            quality_checks: Quality check results
            completeness: Field completeness ratio
            validation_errors: List of validation errors

        Returns:
            float: Confidence score (0.0-1.0)
        """
        # Start with base confidence from response
        base_confidence = 1.0 if response.finish_reason == "stop" else 0.5

        # Apply quality check penalty
        passed_checks = sum(1 for v in quality_checks.values() if v)
        total_checks = len(quality_checks)
        quality_score = passed_checks / total_checks if total_checks > 0 else 0.0

        # Apply completeness factor
        completeness_factor = completeness

        # Apply validation error penalty
        validation_penalty = 1.0
        if validation_errors:
            # Reduce confidence by 10% per validation error (max 50% reduction)
            validation_penalty = max(0.5, 1.0 - (len(validation_errors) * 0.1))

        # Calculate final confidence
        confidence = base_confidence * quality_score * completeness_factor * validation_penalty

        # Ensure confidence is between 0.0 and 1.0
        return max(0.0, min(1.0, confidence))
