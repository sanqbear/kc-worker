# Quick Reference: Prompts and Postprocessors

This is a quick reference guide for using prompt templates and postprocessors in the AI Worker service.

## Import Statements

```python
# Prompt templates
from llm.prompts import SummarizePrompt, KeywordsPrompt, NormalizePrompt

# Postprocessors
from postprocess import SummarizePostprocessor, KeywordsPostprocessor, NormalizePostprocessor

# LLM client
from llm.client import LLMClient
from llm.response import LLMResponse
```

## Summarization

### Basic Usage

```python
# Build prompt
prompt = SummarizePrompt()
user_prompt = prompt.build(text="긴 텍스트...", max_length=200)

# Call LLM
response = await llm_client.generate(
    system_prompt=prompt.system_prompt,
    user_prompt=user_prompt,
    temperature=0.3
)

# Process response
processor = SummarizePostprocessor()
result = processor.process(
    response=response,
    max_length=200,
    original_length=len(text)
)

# Use result
summary = result["summary"]
confidence = result["confidence"]
```

### With Context

```python
user_prompt = prompt.build_with_context(
    text="긴 텍스트...",
    max_length=200,
    context="티켓 내용"
)
```

### Result Structure

```python
{
    "summary": str,
    "length": int,
    "word_count": int,
    "compression_ratio": float,
    "confidence": float,  # 0.0-1.0
    "quality_checks": {
        "not_empty": bool,
        "minimum_length": bool,
        "respects_max_length": bool,
        "completed_normally": bool,
        "not_truncated": bool,
        "contains_content": bool
    }
}
```

## Keyword Extraction

### Basic Usage

```python
# Build prompt
prompt = KeywordsPrompt()
user_prompt = prompt.build(text="텍스트...", max_keywords=10)

# Call LLM
response = await llm_client.generate(
    system_prompt=prompt.system_prompt,
    user_prompt=user_prompt,
    temperature=0.2
)

# Process response
processor = KeywordsPostprocessor()
result = processor.process(
    response=response,
    max_keywords=10,
    min_keyword_length=2,
    deduplicate=True
)

# Use result
keywords = result["keywords"]
confidence = result["confidence"]
```

### With Domain Context

```python
user_prompt = prompt.build_with_domain(
    text="텍스트...",
    max_keywords=10,
    domain="프론트엔드 개발"
)
```

### Multilingual Support

```python
user_prompt = prompt.build_multilingual(
    text="Mixed Korean and English text...",
    max_keywords=10,
    include_english=True
)
```

### Result Structure

```python
{
    "keywords": list[str],
    "count": int,
    "confidence": float,  # 0.0-1.0
    "parsing_info": {
        "success": bool,
        "method": str,  # "json", "markdown_json", "comma_separated", etc.
        "error": str | None
    },
    "quality_checks": {
        "parsing_succeeded": bool,
        "keywords_found": bool,
        "reasonable_count": bool,
        "completed_normally": bool,
        "diverse_keywords": bool,
        "quality_keywords": bool
    }
}
```

## JSON Normalization

### Basic Usage

```python
# Define schema
schema = {
    "name": "string",
    "email": "string",
    "age": "integer"
}

# Build prompt
prompt = NormalizePrompt()
user_prompt = prompt.build(text="자연어 텍스트...", schema=schema)

# Call LLM
response = await llm_client.generate(
    system_prompt=prompt.system_prompt,
    user_prompt=user_prompt,
    temperature=0.1
)

# Process response
processor = NormalizePostprocessor()
result = processor.process(
    response=response,
    schema=schema,
    strict_validation=True,
    allow_extra_fields=False
)

# Use result
data = result["data"]
confidence = result["confidence"]
completeness = result["completeness"]
```

### With Field Descriptions

```python
field_descriptions = {
    "name": "사용자의 전체 이름",
    "email": "이메일 주소",
    "age": "나이 (숫자)"
}

user_prompt = prompt.build_with_field_descriptions(
    text="텍스트...",
    schema=schema,
    field_descriptions=field_descriptions
)
```

### With Examples

```python
examples = [
    {
        "input": "김철수, kim@example.com, 30세",
        "output": {"name": "김철수", "email": "kim@example.com", "age": 30}
    }
]

user_prompt = prompt.build_with_examples(
    text="텍스트...",
    schema=schema,
    examples=examples
)
```

### Result Structure

```python
{
    "data": dict,
    "confidence": float,  # 0.0-1.0
    "completeness": float,  # 0.0-1.0
    "validation_errors": list[str],
    "quality_metrics": {
        "total_fields": int,
        "filled_fields": int,
        "null_fields": int,
        "empty_fields": int,
        "field_coverage": float
    },
    "quality_checks": {
        "parsing_succeeded": bool,
        "data_found": bool,
        "schema_valid": bool,
        "completed_normally": bool,
        "acceptable_completeness": bool,
        "high_completeness": bool
    },
    "parsing_info": {
        "success": bool,
        "method": str,
        "error": str | None
    }
}
```

## Temperature Recommendations

| Task | Temperature | Reason |
|------|-------------|--------|
| Summarization | 0.2-0.4 | Factual, deterministic summaries |
| Keywords | 0.1-0.3 | Consistent keyword extraction |
| Normalization | 0.0-0.2 | Strict structured output |

## Error Handling Pattern

```python
from utils.retry import retry_with_backoff

@retry_with_backoff(max_attempts=3, backoff_factor=2.0)
async def process_with_retry(task_data: dict) -> dict:
    # Build prompt
    prompt = SummarizePrompt()
    user_prompt = prompt.build(**task_data)

    # Call LLM
    response = await llm_client.generate(
        system_prompt=prompt.system_prompt,
        user_prompt=user_prompt,
        temperature=0.3
    )

    # Process
    processor = SummarizePostprocessor()
    result = processor.process(response)

    # Validate quality
    if result["confidence"] < 0.7:
        raise ValueError(f"Low confidence: {result['confidence']}")

    return result

# Usage
try:
    result = await process_with_retry(task_data)
except Exception as e:
    logger.error(f"Processing failed after retries: {e}")
    # Fallback or escalate
```

## Quality Thresholds

### Recommended Minimums

- **Confidence**: 0.7 (retry if lower)
- **Completeness** (normalization): 0.7 (warn if lower)
- **Compression Ratio** (summary): 0.1-0.5 (warn if outside)

### Decision Tree

```python
if result["confidence"] >= 0.9:
    # High quality - use immediately
    return result

elif result["confidence"] >= 0.7:
    # Good quality - use with logging
    logger.info(f"Good quality result: {result['confidence']}")
    return result

elif result["confidence"] >= 0.5:
    # Medium quality - retry once
    logger.warning(f"Medium confidence: {result['confidence']}")
    # Retry with adjusted parameters
    return await retry_with_different_params()

else:
    # Low quality - escalate or fail
    logger.error(f"Low confidence: {result['confidence']}")
    raise ValueError("Quality too low for automatic processing")
```

## Common Patterns

### Batch Processing

```python
async def process_batch(texts: list[str]) -> list[dict]:
    prompt = SummarizePrompt()
    processor = SummarizePostprocessor()
    results = []

    for text in texts:
        user_prompt = prompt.build(text=text, max_length=200)
        response = await llm_client.generate(
            system_prompt=prompt.system_prompt,
            user_prompt=user_prompt,
            temperature=0.3
        )
        result = processor.process(response, max_length=200)
        results.append(result)

    return results
```

### Conditional Retry

```python
async def process_with_conditional_retry(text: str, max_attempts: int = 3) -> dict:
    prompt = SummarizePrompt()
    processor = SummarizePostprocessor()

    for attempt in range(max_attempts):
        # Increase temperature slightly on retry
        temperature = 0.3 + (attempt * 0.1)

        user_prompt = prompt.build(text=text, max_length=200)
        response = await llm_client.generate(
            system_prompt=prompt.system_prompt,
            user_prompt=user_prompt,
            temperature=temperature
        )
        result = processor.process(response, max_length=200)

        if result["confidence"] >= 0.7:
            return result

        logger.warning(
            f"Attempt {attempt + 1}/{max_attempts}: "
            f"confidence={result['confidence']:.2f}"
        )

    raise ValueError(f"Failed after {max_attempts} attempts")
```

### Logging Best Practices

```python
import logging

logger = logging.getLogger(__name__)

# Before processing
logger.info(
    f"Processing {task_type} task",
    extra={
        "task_id": task_id,
        "text_length": len(text),
        "parameters": task_params
    }
)

# After processing
logger.info(
    f"Task completed successfully",
    extra={
        "task_id": task_id,
        "confidence": result["confidence"],
        "processing_time_ms": elapsed_ms
    }
)

# On error
logger.error(
    f"Task processing failed",
    extra={
        "task_id": task_id,
        "error": str(e),
        "quality_checks": result.get("quality_checks")
    },
    exc_info=True
)
```

## Testing Checklist

When implementing a new task processor:

- [ ] Test with valid inputs
- [ ] Test with empty/None inputs
- [ ] Test with malformed LLM responses
- [ ] Test quality threshold handling
- [ ] Test retry logic
- [ ] Test logging output
- [ ] Verify metrics collection
- [ ] Check error handling paths
- [ ] Validate confidence scoring
- [ ] Test edge cases (very short/long inputs)

## Performance Tips

1. **Cache system prompts** - they don't change
2. **Reuse prompt builders** - create once, use many times
3. **Batch similar requests** - reduce API calls
4. **Use appropriate timeouts** - don't wait forever
5. **Monitor token usage** - especially for normalization
6. **Implement rate limiting** - respect API limits
7. **Use connection pooling** - for HTTP clients
8. **Profile postprocessors** - ensure they're fast (<5ms)

## Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Low confidence | Unclear prompt | Add more context or examples |
| Parsing failed | Malformed JSON | Check LLM temperature (use lower) |
| Truncated summary | Max tokens too low | Increase max_tokens in LLM call |
| Missing keywords | Text too short | Reduce max_keywords |
| Validation errors | Schema mismatch | Provide field descriptions |
| Empty response | LLM error | Check API status, retry |

## Additional Resources

- Full documentation: [PROMPTS_AND_POSTPROCESSORS.md](./PROMPTS_AND_POSTPROCESSORS.md)
- Usage examples: [../examples/prompt_usage.py](../examples/prompt_usage.py)
- Integration guide: [../examples/integration_example.py](../examples/integration_example.py)
- Unit tests: [../tests/unit/test_prompts.py](../tests/unit/test_prompts.py)
