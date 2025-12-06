# Prompt Templates and Postprocessors

This document describes the prompt template and postprocessor system for the AI Worker service. These components ensure consistent, high-quality interactions with LLMs and robust extraction of structured data from responses.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Prompt Templates](#prompt-templates)
- [Postprocessors](#postprocessors)
- [Usage Examples](#usage-examples)
- [Testing](#testing)
- [Best Practices](#best-practices)

## Overview

The system consists of two main components:

1. **Prompt Templates**: Generate consistent, well-structured prompts for different LLM tasks
2. **Postprocessors**: Extract and validate structured data from LLM responses

All prompts are written in Korean to match the Knowledge Center's primary language.

## Architecture

```
llm/prompts/
├── __init__.py          # Exports all prompt templates
├── base.py              # Base class with validation
├── summarize.py         # Text summarization prompts
├── keywords.py          # Keyword extraction prompts
└── normalize.py         # JSON normalization prompts

postprocess/
├── __init__.py          # Exports all postprocessors
├── base.py              # Base class with confidence calculation
├── summarize.py         # Summary validation and metrics
├── keywords.py          # Keyword parsing and cleaning
└── normalize.py         # JSON validation and schema checking
```

## Prompt Templates

### Base Class

All prompt templates inherit from `PromptTemplate`:

```python
from abc import ABC, abstractmethod
from typing import Any

class PromptTemplate(ABC):
    @abstractmethod
    def build(self, **kwargs) -> str:
        """Build prompt from input data"""
        pass

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """System prompt for the task"""
        pass
```

### SummarizePrompt

**Purpose**: Generate prompts for text summarization tasks.

**Features**:
- Korean language instructions
- Configurable max_length constraints
- Optional context information (e.g., document type)
- Preserves key information and context
- Prevents hallucination (no adding information)

**Methods**:
- `build(text, max_length=None)`: Basic summarization prompt
- `build_with_context(text, max_length=None, context=None)`: Include document type context

**Example**:
```python
from llm.prompts import SummarizePrompt

prompt = SummarizePrompt()

# Basic usage
user_prompt = prompt.build(
    text="긴 티켓 내용...",
    max_length=200
)

# With context
user_prompt = prompt.build_with_context(
    text="긴 티켓 내용...",
    max_length=200,
    context="고객 지원 티켓"
)

system_prompt = prompt.system_prompt
```

### KeywordsPrompt

**Purpose**: Generate prompts for keyword extraction tasks.

**Features**:
- Extracts meaningful, searchable keywords
- Returns JSON array format
- Prioritizes domain-specific terms
- Supports multilingual keywords
- Configurable keyword count

**Methods**:
- `build(text, max_keywords=10)`: Basic keyword extraction
- `build_with_domain(text, max_keywords=10, domain=None)`: Domain-specific extraction
- `build_multilingual(text, max_keywords=10, include_english=False)`: Multilingual support

**Example**:
```python
from llm.prompts import KeywordsPrompt

prompt = KeywordsPrompt()

# Basic usage
user_prompt = prompt.build(
    text="Vue 3와 TypeScript를 사용한 프로젝트",
    max_keywords=8
)

# With domain context
user_prompt = prompt.build_with_domain(
    text="프로젝트 설명...",
    max_keywords=10,
    domain="프론트엔드 개발"
)
```

### NormalizePrompt

**Purpose**: Convert natural language to structured JSON.

**Features**:
- Schema-driven extraction
- Handles missing information (null values)
- Type-safe output
- Example-based learning
- Field descriptions for clarity

**Methods**:
- `build(text, schema)`: Basic normalization
- `build_with_examples(text, schema, examples=None)`: Include examples
- `build_with_field_descriptions(text, schema, field_descriptions=None)`: Detailed field guidance

**Example**:
```python
from llm.prompts import NormalizePrompt

prompt = NormalizePrompt()

schema = {
    "name": "string",
    "email": "string",
    "department": "string"
}

user_prompt = prompt.build(
    text="김철수, kim@example.com, IT 부서",
    schema=schema
)

# With field descriptions
field_descriptions = {
    "name": "사용자의 전체 이름",
    "email": "이메일 주소",
    "department": "소속 부서명"
}

user_prompt = prompt.build_with_field_descriptions(
    text="김철수, kim@example.com, IT 부서",
    schema=schema,
    field_descriptions=field_descriptions
)
```

## Postprocessors

### Base Class

All postprocessors inherit from `Postprocessor`:

```python
from abc import ABC, abstractmethod
from typing import Any
from llm.response import LLMResponse

class Postprocessor(ABC):
    @abstractmethod
    def process(self, response: LLMResponse, **kwargs) -> dict[str, Any]:
        """Process LLM response and extract structured data"""
        pass
```

### SummarizePostprocessor

**Purpose**: Extract and validate summary text from LLM responses.

**Features**:
- Removes common prefixes (요약:, Summary:, etc.)
- Cleans markdown formatting
- Calculates compression ratio
- Detects truncation
- Quality validation checks

**Output Structure**:
```python
{
    "summary": str,              # Cleaned summary text
    "length": int,               # Character count
    "word_count": int,           # Word count
    "compression_ratio": float,  # summary_length / original_length
    "confidence": float,         # 0.0-1.0
    "quality_checks": {
        "not_empty": bool,
        "minimum_length": bool,
        "respects_max_length": bool,
        "completed_normally": bool,
        "not_truncated": bool,
        "contains_content": bool
    },
    "metadata": {...}
}
```

**Example**:
```python
from postprocess import SummarizePostprocessor

processor = SummarizePostprocessor()

result = processor.process(
    response=llm_response,
    max_length=200,
    original_length=1000
)

print(f"Summary: {result['summary']}")
print(f"Confidence: {result['confidence']:.2f}")
print(f"Compression: {result['compression_ratio']:.2%}")
```

### KeywordsPostprocessor

**Purpose**: Parse and clean keyword arrays from LLM responses.

**Features**:
- Multiple parsing strategies (JSON, markdown, comma-separated, line-separated)
- Graceful fallback for malformed responses
- Case-insensitive deduplication
- Minimum length filtering
- Metadata removal

**Parsing Strategies** (in order):
1. Direct JSON parsing
2. Extract from markdown code blocks
3. Pattern matching for JSON arrays
4. Comma-separated parsing
5. Line-separated parsing

**Output Structure**:
```python
{
    "keywords": list[str],       # Cleaned keyword list
    "count": int,                # Number of keywords
    "confidence": float,         # 0.0-1.0
    "quality_checks": {
        "parsing_succeeded": bool,
        "keywords_found": bool,
        "reasonable_count": bool,
        "completed_normally": bool,
        "diverse_keywords": bool,
        "quality_keywords": bool
    },
    "parsing_info": {
        "success": bool,
        "method": str,           # "json", "markdown_json", etc.
        "error": str | None
    },
    "metadata": {...}
}
```

**Example**:
```python
from postprocess import KeywordsPostprocessor

processor = KeywordsPostprocessor()

result = processor.process(
    response=llm_response,
    max_keywords=10,
    min_keyword_length=2,
    deduplicate=True
)

print(f"Keywords: {result['keywords']}")
print(f"Parsing method: {result['parsing_info']['method']}")
```

### NormalizePostprocessor

**Purpose**: Validate and score JSON normalization results.

**Features**:
- Multiple JSON parsing strategies
- Schema validation (strict or lenient)
- Type checking
- Completeness calculation
- Quality metrics
- Confidence scoring

**Output Structure**:
```python
{
    "data": dict,                # Extracted JSON data
    "confidence": float,         # 0.0-1.0
    "completeness": float,       # 0.0-1.0 (filled fields ratio)
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
    "validation_errors": list[str],
    "parsing_info": {
        "success": bool,
        "method": str,
        "error": str | None
    },
    "metadata": {...}
}
```

**Example**:
```python
from postprocess import NormalizePostprocessor

processor = NormalizePostprocessor()

schema = {
    "name": "string",
    "email": "string",
    "age": "integer"
}

result = processor.process(
    response=llm_response,
    schema=schema,
    strict_validation=True,
    allow_extra_fields=False
)

print(f"Data: {result['data']}")
print(f"Completeness: {result['completeness']:.2%}")
print(f"Confidence: {result['confidence']:.2f}")
print(f"Errors: {result['validation_errors']}")
```

## Usage Examples

### Complete Workflow: Summarization

```python
from llm.client import LLMClient
from llm.prompts import SummarizePrompt
from postprocess import SummarizePostprocessor

# 1. Build prompt
prompt_builder = SummarizePrompt()
system_prompt = prompt_builder.system_prompt
user_prompt = prompt_builder.build(
    text=long_ticket_description,
    max_length=200
)

# 2. Call LLM
client = LLMClient()
response = await client.generate(
    model="gpt-4",
    system_prompt=system_prompt,
    user_prompt=user_prompt,
    temperature=0.3
)

# 3. Process response
processor = SummarizePostprocessor()
result = processor.process(
    response=response,
    max_length=200,
    original_length=len(long_ticket_description)
)

# 4. Use results
if result["confidence"] > 0.7:
    save_summary(result["summary"])
else:
    logger.warning(f"Low confidence: {result['confidence']}")
```

### Complete Workflow: Keyword Extraction

```python
from llm.client import LLMClient
from llm.prompts import KeywordsPrompt
from postprocess import KeywordsPostprocessor

# 1. Build prompt
prompt_builder = KeywordsPrompt()
system_prompt = prompt_builder.system_prompt
user_prompt = prompt_builder.build_with_domain(
    text=document_content,
    max_keywords=10,
    domain="기술 문서"
)

# 2. Call LLM
client = LLMClient()
response = await client.generate(
    model="gpt-4",
    system_prompt=system_prompt,
    user_prompt=user_prompt,
    temperature=0.2
)

# 3. Process response
processor = KeywordsPostprocessor()
result = processor.process(
    response=response,
    max_keywords=10,
    min_keyword_length=2,
    deduplicate=True
)

# 4. Use results
if result["parsing_info"]["success"]:
    save_keywords(result["keywords"])
else:
    logger.error(f"Parsing failed: {result['parsing_info']['error']}")
```

### Complete Workflow: JSON Normalization

```python
from llm.client import LLMClient
from llm.prompts import NormalizePrompt
from postprocess import NormalizePostprocessor

# 1. Define schema
schema = {
    "title": "string",
    "priority": "string",
    "category": "string",
    "assignee": "string"
}

# 2. Build prompt
prompt_builder = NormalizePrompt()
system_prompt = prompt_builder.system_prompt
user_prompt = prompt_builder.build(
    text=unstructured_ticket_data,
    schema=schema
)

# 3. Call LLM
client = LLMClient()
response = await client.generate(
    model="gpt-4",
    system_prompt=system_prompt,
    user_prompt=user_prompt,
    temperature=0.1
)

# 4. Process response
processor = NormalizePostprocessor()
result = processor.process(
    response=response,
    schema=schema,
    strict_validation=True,
    allow_extra_fields=False
)

# 5. Use results
if result["confidence"] > 0.8 and result["completeness"] > 0.7:
    create_ticket(result["data"])
else:
    logger.warning(
        f"Low quality: confidence={result['confidence']:.2f}, "
        f"completeness={result['completeness']:.2f}"
    )
```

## Testing

### Running Tests

```bash
# Run all prompt and postprocessor tests
pytest tests/unit/test_prompts.py tests/unit/test_postprocessors.py -v

# Run specific test class
pytest tests/unit/test_prompts.py::TestSummarizePrompt -v

# Run with coverage
pytest tests/unit/test_prompts.py tests/unit/test_postprocessors.py --cov=llm.prompts --cov=postprocess
```

### Test Coverage

The test suite covers:
- Valid input handling
- Error handling (empty, None, invalid inputs)
- Edge cases (truncation, malformed JSON, etc.)
- Quality checks
- Confidence scoring
- Multiple parsing strategies

## Best Practices

### Prompt Design

1. **Be Specific**: Clearly define the task and expected output format
2. **Provide Examples**: Include examples for complex tasks (normalization)
3. **Constrain Output**: Specify length limits, format requirements
4. **Language Consistency**: Keep all Korean prompts natural and professional
5. **Prevent Hallucination**: Explicitly instruct to only use provided information

### Postprocessing

1. **Multiple Strategies**: Always implement fallback parsing methods
2. **Graceful Degradation**: Don't fail on malformed responses; try to extract what you can
3. **Quality Checks**: Always validate output quality before using results
4. **Confidence Scoring**: Use confidence scores to make decisions (retry, manual review, etc.)
5. **Logging**: Log parsing methods and errors for debugging

### Error Handling

```python
try:
    result = processor.process(response, **params)

    if result["confidence"] < 0.7:
        logger.warning(f"Low confidence: {result['confidence']}")
        # Maybe retry or escalate

    if result.get("validation_errors"):
        logger.error(f"Validation errors: {result['validation_errors']}")
        # Handle specific errors

    return result

except ValueError as e:
    logger.error(f"Processing failed: {e}")
    # Fallback behavior
```

### Temperature Settings

Recommended temperature values for different tasks:

- **Summarization**: 0.2-0.4 (factual, deterministic)
- **Keywords**: 0.1-0.3 (consistent extraction)
- **Normalization**: 0.0-0.2 (strict structured output)

### Retry Logic

```python
from utils.retry import retry_with_backoff

@retry_with_backoff(max_attempts=3, backoff_factor=2.0)
async def extract_keywords_with_retry(text: str) -> dict:
    # Build prompt
    prompt_builder = KeywordsPrompt()
    user_prompt = prompt_builder.build(text=text, max_keywords=10)

    # Call LLM
    response = await llm_client.generate(
        system_prompt=prompt_builder.system_prompt,
        user_prompt=user_prompt,
        temperature=0.2
    )

    # Process
    processor = KeywordsPostprocessor()
    result = processor.process(response, max_keywords=10)

    # Raise if quality too low (triggers retry)
    if result["confidence"] < 0.5:
        raise ValueError(f"Low confidence: {result['confidence']}")

    return result
```

## Performance Considerations

### Prompt Token Usage

- **Summarization**: Moderate (system + text)
- **Keywords**: Low (system + text)
- **Normalization**: High (system + schema + examples + text)

To optimize:
- Cache system prompts
- Reuse prompt builders
- Batch similar requests

### Postprocessing Performance

All postprocessors are designed for speed:
- Regex-based parsing (microseconds)
- Single-pass validation
- Minimal memory allocation

Typical processing times:
- Summary: < 1ms
- Keywords: < 2ms
- Normalization: < 5ms

## Extending the System

### Adding a New Prompt Template

```python
from llm.prompts.base import PromptTemplate

class CustomPrompt(PromptTemplate):
    @property
    def system_prompt(self) -> str:
        return """당신은 [역할]입니다.

        [작업 설명]

        [원칙들]
        """

    def build(self, **kwargs) -> str:
        self.validate_params(["required_param"], kwargs)
        # Build and return prompt
        return f"[프롬프트 템플릿] {kwargs['required_param']}"
```

### Adding a New Postprocessor

```python
from postprocess.base import Postprocessor
from llm.response import LLMResponse

class CustomPostprocessor(Postprocessor):
    def process(self, response: LLMResponse, **kwargs) -> dict:
        self.validate_response(response)

        # Extract data
        data = self._extract_data(response.content)

        # Validate
        quality_checks = self._validate(data)

        # Calculate confidence
        confidence = self.calculate_confidence(response, quality_checks)

        return {
            "data": data,
            "confidence": confidence,
            "quality_checks": quality_checks
        }
```

## Troubleshooting

### Common Issues

**Issue**: Keywords not parsing correctly
- **Solution**: Check `parsing_info["method"]` and `parsing_info["error"]`
- **Fix**: Adjust prompt to be more explicit about JSON format

**Issue**: Low confidence scores
- **Solution**: Review `quality_checks` to see which checks failed
- **Fix**: Adjust prompt clarity or LLM temperature

**Issue**: Validation errors in normalization
- **Solution**: Check `validation_errors` for specific issues
- **Fix**: Add field descriptions or examples to prompt

**Issue**: Truncated summaries
- **Solution**: Check `quality_checks["not_truncated"]`
- **Fix**: Increase max_length or adjust LLM max_tokens

## Related Documentation

- [LLM Client Documentation](./LLM_CLIENT.md)
- [Task Processing Guide](./TASK_PROCESSING.md)
- [Worker Architecture](./ARCHITECTURE.md)
