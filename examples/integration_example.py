"""Integration example showing how prompts and postprocessors work with task processors.

This example demonstrates the complete flow from task receipt to result storage,
including error handling and retry logic.
"""

import asyncio
import logging
from typing import Any

from llm.client import LLMClient
from llm.prompts import SummarizePrompt, KeywordsPrompt, NormalizePrompt
from postprocess import SummarizePostprocessor, KeywordsPostprocessor, NormalizePostprocessor
from llm.response import LLMResponse
from utils.retry import retry_with_backoff

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TaskProcessor:
    """Base task processor with LLM integration."""

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    @retry_with_backoff(max_attempts=3, backoff_factor=2.0)
    async def call_llm_with_retry(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        model: str = "gpt-4"
    ) -> LLMResponse:
        """Call LLM with retry logic.

        Args:
            system_prompt: System prompt
            user_prompt: User prompt
            temperature: Sampling temperature
            model: Model name

        Returns:
            LLMResponse object
        """
        logger.info(f"Calling LLM with model={model}, temp={temperature}")

        response = await self.llm_client.generate(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature
        )

        logger.info(
            f"LLM response received: finish_reason={response.finish_reason}, "
            f"tokens={response.usage.get('total_tokens', 'unknown')}"
        )

        return response


class SummarizeTaskProcessor(TaskProcessor):
    """Process summarization tasks."""

    def __init__(self, llm_client: LLMClient):
        super().__init__(llm_client)
        self.prompt_builder = SummarizePrompt()
        self.postprocessor = SummarizePostprocessor()

    async def process(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Process a summarization task.

        Args:
            task_data: Task data containing:
                - text (str): Text to summarize
                - max_length (int, optional): Max summary length
                - context (str, optional): Document context

        Returns:
            dict: Processing result with summary and metadata
        """
        text = task_data.get("text")
        max_length = task_data.get("max_length")
        context = task_data.get("context")

        if not text:
            raise ValueError("Task data missing 'text' field")

        logger.info(f"Processing summarization task: length={len(text)}, max_length={max_length}")

        # Build prompt
        if context:
            user_prompt = self.prompt_builder.build_with_context(
                text=text,
                max_length=max_length,
                context=context
            )
        else:
            user_prompt = self.prompt_builder.build(
                text=text,
                max_length=max_length
            )

        # Call LLM
        response = await self.call_llm_with_retry(
            system_prompt=self.prompt_builder.system_prompt,
            user_prompt=user_prompt,
            temperature=0.3
        )

        # Postprocess
        result = self.postprocessor.process(
            response=response,
            max_length=max_length,
            original_length=len(text)
        )

        # Validate quality
        if result["confidence"] < 0.7:
            logger.warning(
                f"Low confidence summary: {result['confidence']:.2f}, "
                f"checks={result['quality_checks']}"
            )

        # Log metrics
        logger.info(
            f"Summary generated: length={result['length']}, "
            f"compression={result['compression_ratio']:.2%}, "
            f"confidence={result['confidence']:.2f}"
        )

        return {
            "success": True,
            "summary": result["summary"],
            "length": result["length"],
            "compression_ratio": result["compression_ratio"],
            "confidence": result["confidence"],
            "quality_checks": result["quality_checks"],
            "metadata": result["metadata"]
        }


class KeywordsTaskProcessor(TaskProcessor):
    """Process keyword extraction tasks."""

    def __init__(self, llm_client: LLMClient):
        super().__init__(llm_client)
        self.prompt_builder = KeywordsPrompt()
        self.postprocessor = KeywordsPostprocessor()

    async def process(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Process a keyword extraction task.

        Args:
            task_data: Task data containing:
                - text (str): Text to extract keywords from
                - max_keywords (int): Maximum number of keywords
                - domain (str, optional): Domain context
                - include_english (bool, optional): Include English keywords

        Returns:
            dict: Processing result with keywords and metadata
        """
        text = task_data.get("text")
        max_keywords = task_data.get("max_keywords", 10)
        domain = task_data.get("domain")
        include_english = task_data.get("include_english", False)

        if not text:
            raise ValueError("Task data missing 'text' field")

        logger.info(
            f"Processing keyword extraction task: length={len(text)}, "
            f"max_keywords={max_keywords}, domain={domain}"
        )

        # Build prompt
        if include_english:
            user_prompt = self.prompt_builder.build_multilingual(
                text=text,
                max_keywords=max_keywords,
                include_english=True
            )
        elif domain:
            user_prompt = self.prompt_builder.build_with_domain(
                text=text,
                max_keywords=max_keywords,
                domain=domain
            )
        else:
            user_prompt = self.prompt_builder.build(
                text=text,
                max_keywords=max_keywords
            )

        # Call LLM
        response = await self.call_llm_with_retry(
            system_prompt=self.prompt_builder.system_prompt,
            user_prompt=user_prompt,
            temperature=0.2
        )

        # Postprocess
        result = self.postprocessor.process(
            response=response,
            max_keywords=max_keywords,
            min_keyword_length=2,
            deduplicate=True
        )

        # Validate parsing
        if not result["parsing_info"]["success"]:
            logger.error(
                f"Keyword parsing failed: {result['parsing_info']['error']}, "
                f"response={response.content[:100]}"
            )
            raise ValueError(f"Failed to parse keywords: {result['parsing_info']['error']}")

        # Validate quality
        if result["confidence"] < 0.6:
            logger.warning(
                f"Low confidence keywords: {result['confidence']:.2f}, "
                f"checks={result['quality_checks']}"
            )

        # Log metrics
        logger.info(
            f"Keywords extracted: count={result['count']}, "
            f"method={result['parsing_info']['method']}, "
            f"confidence={result['confidence']:.2f}"
        )

        return {
            "success": True,
            "keywords": result["keywords"],
            "count": result["count"],
            "confidence": result["confidence"],
            "parsing_method": result["parsing_info"]["method"],
            "quality_checks": result["quality_checks"],
            "metadata": result["metadata"]
        }


class NormalizeTaskProcessor(TaskProcessor):
    """Process JSON normalization tasks."""

    def __init__(self, llm_client: LLMClient):
        super().__init__(llm_client)
        self.prompt_builder = NormalizePrompt()
        self.postprocessor = NormalizePostprocessor()

    async def process(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Process a JSON normalization task.

        Args:
            task_data: Task data containing:
                - text (str): Natural language text
                - schema (dict): Target JSON schema
                - field_descriptions (dict, optional): Field descriptions
                - examples (list, optional): Example input/output pairs

        Returns:
            dict: Processing result with normalized data and metadata
        """
        text = task_data.get("text")
        schema = task_data.get("schema")
        field_descriptions = task_data.get("field_descriptions")
        examples = task_data.get("examples")

        if not text:
            raise ValueError("Task data missing 'text' field")
        if not schema:
            raise ValueError("Task data missing 'schema' field")

        logger.info(
            f"Processing normalization task: length={len(text)}, "
            f"schema_fields={len(schema)}"
        )

        # Build prompt
        if field_descriptions:
            user_prompt = self.prompt_builder.build_with_field_descriptions(
                text=text,
                schema=schema,
                field_descriptions=field_descriptions
            )
        elif examples:
            user_prompt = self.prompt_builder.build_with_examples(
                text=text,
                schema=schema,
                examples=examples
            )
        else:
            user_prompt = self.prompt_builder.build(
                text=text,
                schema=schema
            )

        # Call LLM
        response = await self.call_llm_with_retry(
            system_prompt=self.prompt_builder.system_prompt,
            user_prompt=user_prompt,
            temperature=0.1  # Very low for structured output
        )

        # Postprocess
        result = self.postprocessor.process(
            response=response,
            schema=schema,
            strict_validation=True,
            allow_extra_fields=False
        )

        # Validate parsing
        if not result["parsing_info"]["success"]:
            logger.error(
                f"JSON parsing failed: {result['parsing_info']['error']}, "
                f"response={response.content[:100]}"
            )
            raise ValueError(f"Failed to parse JSON: {result['parsing_info']['error']}")

        # Validate schema
        if result["validation_errors"]:
            logger.warning(
                f"Schema validation errors: {result['validation_errors']}"
            )

        # Check quality thresholds
        if result["confidence"] < 0.7 or result["completeness"] < 0.7:
            logger.warning(
                f"Low quality normalization: confidence={result['confidence']:.2f}, "
                f"completeness={result['completeness']:.2f}"
            )

        # Log metrics
        logger.info(
            f"JSON normalized: completeness={result['completeness']:.2%}, "
            f"confidence={result['confidence']:.2f}, "
            f"filled_fields={result['quality_metrics']['filled_fields']}/{result['quality_metrics']['total_fields']}"
        )

        return {
            "success": True,
            "data": result["data"],
            "confidence": result["confidence"],
            "completeness": result["completeness"],
            "validation_errors": result["validation_errors"],
            "quality_metrics": result["quality_metrics"],
            "quality_checks": result["quality_checks"],
            "metadata": result["metadata"]
        }


# Example usage
async def main():
    """Run example task processing."""
    # Initialize LLM client
    llm_client = LLMClient(api_key="your-api-key")

    # Example 1: Summarization
    print("=" * 60)
    print("Example 1: Summarization")
    print("=" * 60)

    summarize_processor = SummarizeTaskProcessor(llm_client)
    summarize_task = {
        "text": """
        사용자가 로그인 후 대시보드 페이지에서 500 에러가 발생합니다.
        브라우저 콘솔을 확인한 결과 /api/dashboard/stats 엔드포인트에서
        에러가 발생하는 것을 확인했습니다. 서버 로그를 보니 데이터베이스
        연결 타임아웃이 발생했습니다. 최근 데이터베이스 서버의 부하가
        증가하여 연결 풀이 고갈된 것으로 보입니다. 긴급하게 연결 풀 크기를
        늘리고 slow query를 최적화해야 합니다.
        """,
        "max_length": 100,
        "context": "고객 지원 티켓"
    }

    try:
        result = await summarize_processor.process(summarize_task)
        print(f"Success: {result['success']}")
        print(f"Summary: {result['summary']}")
        print(f"Confidence: {result['confidence']:.2f}")
        print(f"Compression: {result['compression_ratio']:.2%}")
    except Exception as e:
        logger.error(f"Summarization failed: {e}")

    # Example 2: Keyword Extraction
    print("\n" + "=" * 60)
    print("Example 2: Keyword Extraction")
    print("=" * 60)

    keywords_processor = KeywordsTaskProcessor(llm_client)
    keywords_task = {
        "text": """
        Vue 3 프로젝트에서 Pinia 스토어를 사용하여 상태 관리를 구현했습니다.
        TypeScript와 Composition API를 활용하여 타입 안정성을 확보했고,
        Vite 빌드 도구로 빠른 개발 환경을 구성했습니다. Tailwind CSS로
        스타일링하고 vue-router로 라우팅을 처리합니다.
        """,
        "max_keywords": 8,
        "domain": "프론트엔드 개발"
    }

    try:
        result = await keywords_processor.process(keywords_task)
        print(f"Success: {result['success']}")
        print(f"Keywords: {result['keywords']}")
        print(f"Count: {result['count']}")
        print(f"Parsing method: {result['parsing_method']}")
        print(f"Confidence: {result['confidence']:.2f}")
    except Exception as e:
        logger.error(f"Keyword extraction failed: {e}")

    # Example 3: JSON Normalization
    print("\n" + "=" * 60)
    print("Example 3: JSON Normalization")
    print("=" * 60)

    normalize_processor = NormalizeTaskProcessor(llm_client)
    normalize_task = {
        "text": """
        티켓 제목: 로그인 에러
        우선순위: 높음
        카테고리: 인증
        담당자: 김철수
        상태: 진행중
        """,
        "schema": {
            "title": "string",
            "priority": "string",
            "category": "string",
            "assignee": "string",
            "status": "string"
        },
        "field_descriptions": {
            "title": "티켓 제목",
            "priority": "우선순위 (낮음, 보통, 높음, 긴급)",
            "category": "문제 카테고리",
            "assignee": "담당자 이름",
            "status": "현재 상태 (대기, 진행중, 완료)"
        }
    }

    try:
        result = await normalize_processor.process(normalize_task)
        print(f"Success: {result['success']}")
        print(f"Data: {result['data']}")
        print(f"Confidence: {result['confidence']:.2f}")
        print(f"Completeness: {result['completeness']:.2%}")
        print(f"Validation errors: {result['validation_errors']}")
    except Exception as e:
        logger.error(f"Normalization failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
