"""
JSON normalization task using LLM.

Converts natural language requests into structured JSON according to a provided schema.
This is useful for converting user input into API requests or database queries.
"""

import json
from typing import Any, Dict

from ..celery import app
from ..config import settings
from ..utils.retry import InvalidInputError, SchemaValidationError, exponential_backoff, should_retry
from .base import BaseLLMTask


class NormalizeTask(BaseLLMTask):
    """
    Task for normalizing natural language to structured JSON using LLM.

    Input:
        - request (str): Natural language request from user
        - schema (Dict[str, Any]): JSON schema defining the expected output structure
        - examples (List[Dict], optional): Example input/output pairs for few-shot learning
        - language (str, optional): Language of the request (default: "auto")

    Output:
        - normalized (Dict[str, Any]): The structured JSON conforming to schema
        - confidence (float): Confidence score (0.0-1.0) for the normalization
    """

    name = "celery_app.tasks.normalize.normalize_json"
    max_retries = settings.task_max_retries
    default_retry_delay = settings.task_retry_delay

    def build_prompt(self, **kwargs: Any) -> str:
        """
        Build the JSON normalization prompt.

        Args:
            **kwargs: Must contain 'request' and 'schema', optionally 'examples' and 'language'

        Returns:
            str: The formatted prompt

        Raises:
            InvalidInputError: If required inputs are missing or invalid
        """
        # Validate required inputs
        if "request" not in kwargs:
            raise InvalidInputError("Missing required parameter: request")
        if "schema" not in kwargs:
            raise InvalidInputError("Missing required parameter: schema")

        request_text = kwargs["request"]
        schema = kwargs["schema"]

        if not isinstance(request_text, str) or not request_text.strip():
            raise InvalidInputError("Parameter 'request' must be a non-empty string")
        if not isinstance(schema, dict):
            raise InvalidInputError("Parameter 'schema' must be a dictionary")

        # Get optional parameters
        examples = kwargs.get("examples", [])
        language = kwargs.get("language", "auto")

        # Format schema as JSON string
        schema_json = json.dumps(schema, indent=2, ensure_ascii=False)

        # Build examples section if provided
        examples_section = ""
        if examples and isinstance(examples, list):
            examples_section = "\n\nExamples:\n"
            for i, example in enumerate(examples[:3], 1):  # Limit to 3 examples
                if isinstance(example, dict) and "input" in example and "output" in example:
                    examples_section += f"\nExample {i}:\n"
                    examples_section += f"Input: {example['input']}\n"
                    examples_section += f"Output: {json.dumps(example['output'], ensure_ascii=False)}\n"

        # Build the prompt
        if language == "auto" or language == "en":
            prompt = f"""You are a professional data normalization assistant. Your task is to convert natural language requests into structured JSON format according to the provided schema.

Schema (the JSON output must conform to this structure):
{schema_json}
{examples_section}

Requirements:
- Parse the user's natural language request carefully
- Extract all relevant information
- Map the information to the schema fields
- Use appropriate data types (strings, numbers, booleans, arrays, objects)
- If information is missing, use null or omit optional fields
- Return ONLY valid JSON matching the schema, nothing else
- Do not include explanations or comments

User Request:
{request_text}

Structured JSON (matching the schema):"""
        else:
            # Korean or other languages
            prompt = f"""당신은 전문적인 데이터 정규화 어시스턴트입니다. 자연어 요청을 제공된 스키마에 따라 구조화된 JSON 형식으로 변환하세요.

스키마 (JSON 출력은 이 구조를 따라야 합니다):
{schema_json}
{examples_section}

요구사항:
- 사용자의 자연어 요청을 주의깊게 분석
- 모든 관련 정보 추출
- 정보를 스키마 필드에 매핑
- 적절한 데이터 타입 사용 (문자열, 숫자, 불린, 배열, 객체)
- 정보가 누락된 경우 null 사용 또는 선택적 필드 생략
- 스키마와 일치하는 유효한 JSON만 반환, 다른 내용 없이
- 설명이나 주석 포함 금지

사용자 요청:
{request_text}

구조화된 JSON (스키마와 일치):"""

        return prompt

    def postprocess(self, llm_output: str, **kwargs: Any) -> Dict[str, Any]:
        """
        Postprocess the LLM output into the final result.

        Args:
            llm_output: Raw output from the LLM (expected to be JSON)
            **kwargs: Original task inputs

        Returns:
            Dict[str, Any]: Processed result with normalized JSON

        Raises:
            InvalidInputError: If LLM output is not valid JSON
            SchemaValidationError: If output doesn't match the schema
        """
        # Clean up the output
        output = llm_output.strip()

        # Try to extract JSON from output
        try:
            # Try to parse as JSON directly
            normalized = json.loads(output)
        except json.JSONDecodeError:
            # Try to find JSON object in the output
            import re
            # Look for JSON object
            match = re.search(r'\{.*\}', output, re.DOTALL)
            if match:
                try:
                    normalized = json.loads(match.group(0))
                except json.JSONDecodeError as e:
                    self.logger.error(
                        "Failed to parse JSON",
                        extra={"output": output, "error": str(e)}
                    )
                    raise InvalidInputError(f"Invalid JSON in LLM output: {e}") from e
            else:
                raise InvalidInputError("No valid JSON found in LLM output")

        # Validate that normalized is a dictionary
        if not isinstance(normalized, dict):
            raise InvalidInputError(f"Expected JSON object, got {type(normalized)}")

        # Basic schema validation (check required fields if specified in schema)
        schema = kwargs.get("schema", {})
        if "required" in schema:
            required_fields = schema["required"]
            missing_fields = [field for field in required_fields if field not in normalized]
            if missing_fields:
                raise SchemaValidationError(
                    f"Missing required fields in normalized output: {missing_fields}"
                )

        # Calculate a simple confidence score based on completeness
        confidence = self._calculate_confidence(normalized, schema)

        self.logger.info(
            "JSON normalized",
            extra={
                "field_count": len(normalized),
                "confidence": f"{confidence:.2f}",
            }
        )

        return {
            "normalized": normalized,
            "confidence": round(confidence, 2),
        }

    def _calculate_confidence(self, normalized: Dict[str, Any], schema: Dict[str, Any]) -> float:
        """
        Calculate a confidence score for the normalization.

        This is a simple heuristic based on:
        - Presence of expected fields
        - Non-null values
        - Data type matches (if schema has type info)

        Args:
            normalized: The normalized JSON object
            schema: The target schema

        Returns:
            float: Confidence score between 0.0 and 1.0
        """
        if not schema or "properties" not in schema:
            # No schema to validate against, return moderate confidence
            return 0.8

        properties = schema.get("properties", {})
        if not properties:
            return 0.8

        total_fields = len(properties)
        matched_fields = 0

        for field, field_schema in properties.items():
            if field in normalized:
                value = normalized[field]

                # Check if value is not null/empty
                if value is not None and value != "":
                    matched_fields += 1

                    # Bonus for type matching (if type is specified)
                    if "type" in field_schema:
                        expected_type = field_schema["type"]
                        if self._check_type_match(value, expected_type):
                            matched_fields += 0.1  # Small bonus for correct type

        # Confidence is the ratio of matched fields to total fields
        confidence = matched_fields / total_fields if total_fields > 0 else 0.5

        # Cap at 1.0
        return min(confidence, 1.0)

    def _check_type_match(self, value: Any, expected_type: str) -> bool:
        """
        Check if a value matches the expected JSON schema type.

        Args:
            value: The value to check
            expected_type: Expected type from schema ("string", "number", "boolean", "array", "object")

        Returns:
            bool: True if the type matches
        """
        type_mapping = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        expected_python_type = type_mapping.get(expected_type)
        if expected_python_type is None:
            return True  # Unknown type, assume match

        return isinstance(value, expected_python_type)


@app.task(
    bind=True,
    base=NormalizeTask,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": settings.task_max_retries},
    retry_backoff=True,
    retry_backoff_max=3600,  # Max 1 hour between retries
    retry_jitter=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def normalize_json(self, **kwargs: Any) -> Dict[str, Any]:
    """
    Celery task wrapper for JSON normalization.

    Args:
        request (str): Natural language request from user
        schema (Dict[str, Any]): JSON schema defining the expected output structure
        examples (List[Dict], optional): Example input/output pairs
        language (str, optional): Language of the request (default: "auto")

    Returns:
        Dict[str, Any]: Normalization result

    Example:
        >>> result = normalize_json.delay(
        ...     request="Create a ticket for login issue with high priority",
        ...     schema={
        ...         "properties": {
        ...             "title": {"type": "string"},
        ...             "priority": {"type": "string", "enum": ["low", "medium", "high"]},
        ...             "category": {"type": "string"}
        ...         },
        ...         "required": ["title"]
        ...     }
        ... )
        >>> result.get()
        {
            "normalized": {
                "title": "Login issue",
                "priority": "high",
                "category": "authentication"
            },
            "confidence": 0.95
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
