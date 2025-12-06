"""Example usage of prompt templates and postprocessors.

This module demonstrates how to use the prompt templates and postprocessors
for different LLM tasks.
"""

from llm.prompts import SummarizePrompt, KeywordsPrompt, NormalizePrompt
from postprocess import SummarizePostprocessor, KeywordsPostprocessor, NormalizePostprocessor
from llm.response import LLMResponse


def example_summarize():
    """Example: Summarize a ticket description."""
    print("=== Summarization Example ===\n")

    # Sample ticket text
    ticket_text = """
    사용자가 로그인 후 대시보드 페이지에서 500 에러가 발생합니다.
    브라우저 콘솔을 확인한 결과 /api/dashboard/stats 엔드포인트에서
    에러가 발생하는 것을 확인했습니다. 서버 로그를 보니 데이터베이스
    연결 타임아웃이 발생했습니다. 최근 데이터베이스 서버의 부하가
    증가하여 연결 풀이 고갈된 것으로 보입니다.
    """

    # Create prompt
    prompt_builder = SummarizePrompt()
    system_prompt = prompt_builder.system_prompt
    user_prompt = prompt_builder.build_with_context(
        text=ticket_text,
        max_length=100,
        context="티켓 내용"
    )

    print("System Prompt:")
    print(system_prompt[:200] + "...\n")

    print("User Prompt:")
    print(user_prompt[:200] + "...\n")

    # Simulate LLM response
    llm_response = LLMResponse(
        content="로그인 후 대시보드 페이지에서 데이터베이스 연결 타임아웃으로 인한 500 에러 발생. 연결 풀 고갈이 원인.",
        model="gpt-4",
        finish_reason="stop",
        usage={"prompt_tokens": 150, "completion_tokens": 50, "total_tokens": 200}
    )

    # Process response
    postprocessor = SummarizePostprocessor()
    result = postprocessor.process(
        response=llm_response,
        max_length=100,
        original_length=len(ticket_text)
    )

    print("Processed Result:")
    print(f"Summary: {result['summary']}")
    print(f"Length: {result['length']} chars")
    print(f"Compression Ratio: {result['compression_ratio']:.2%}")
    print(f"Confidence: {result['confidence']:.2f}")
    print(f"Quality Checks: {result['quality_checks']}\n")


def example_keywords():
    """Example: Extract keywords from a document."""
    print("=== Keyword Extraction Example ===\n")

    # Sample document
    document = """
    Vue 3 프로젝트에서 Pinia 스토어를 사용하여 상태 관리를 구현했습니다.
    TypeScript와 Composition API를 활용하여 타입 안정성을 확보했고,
    Vite 빌드 도구로 빠른 개발 환경을 구성했습니다.
    """

    # Create prompt
    prompt_builder = KeywordsPrompt()
    system_prompt = prompt_builder.system_prompt
    user_prompt = prompt_builder.build_with_domain(
        text=document,
        max_keywords=8,
        domain="프론트엔드 개발"
    )

    print("System Prompt:")
    print(system_prompt[:200] + "...\n")

    print("User Prompt:")
    print(user_prompt[:150] + "...\n")

    # Simulate LLM response
    llm_response = LLMResponse(
        content='["Vue 3", "Pinia", "상태 관리", "TypeScript", "Composition API", "타입 안정성", "Vite", "빌드 도구"]',
        model="gpt-4",
        finish_reason="stop",
        usage={"prompt_tokens": 120, "completion_tokens": 40, "total_tokens": 160}
    )

    # Process response
    postprocessor = KeywordsPostprocessor()
    result = postprocessor.process(
        response=llm_response,
        max_keywords=8,
        min_keyword_length=2,
        deduplicate=True
    )

    print("Processed Result:")
    print(f"Keywords: {result['keywords']}")
    print(f"Count: {result['count']}")
    print(f"Confidence: {result['confidence']:.2f}")
    print(f"Parsing Method: {result['parsing_info']['method']}")
    print(f"Quality Checks: {result['quality_checks']}\n")


def example_normalize():
    """Example: Normalize user input to structured JSON."""
    print("=== JSON Normalization Example ===\n")

    # Sample user input
    user_input = """
    이름은 김철수이고, 이메일은 kim@example.com입니다.
    전화번호는 010-1234-5678이고, IT 부서에서 근무합니다.
    관리자 권한이 필요합니다.
    """

    # Define schema
    schema = {
        "name": "string",
        "email": "string",
        "phone": "string",
        "department": "string",
        "role": "string",
        "is_admin": "boolean"
    }

    # Field descriptions
    field_descriptions = {
        "name": "사용자의 전체 이름",
        "email": "이메일 주소",
        "phone": "전화번호 (하이픈 포함)",
        "department": "소속 부서",
        "role": "직책 또는 역할",
        "is_admin": "관리자 권한 여부"
    }

    # Create prompt
    prompt_builder = NormalizePrompt()
    system_prompt = prompt_builder.system_prompt
    user_prompt = prompt_builder.build_with_field_descriptions(
        text=user_input,
        schema=schema,
        field_descriptions=field_descriptions
    )

    print("System Prompt:")
    print(system_prompt[:200] + "...\n")

    print("User Prompt:")
    print(user_prompt[:250] + "...\n")

    # Simulate LLM response
    llm_response = LLMResponse(
        content="""{
  "name": "김철수",
  "email": "kim@example.com",
  "phone": "010-1234-5678",
  "department": "IT",
  "role": null,
  "is_admin": true
}""",
        model="gpt-4",
        finish_reason="stop",
        usage={"prompt_tokens": 200, "completion_tokens": 80, "total_tokens": 280}
    )

    # Process response
    postprocessor = NormalizePostprocessor()
    result = postprocessor.process(
        response=llm_response,
        schema=schema,
        strict_validation=True,
        allow_extra_fields=False
    )

    print("Processed Result:")
    print(f"Data: {result['data']}")
    print(f"Confidence: {result['confidence']:.2f}")
    print(f"Completeness: {result['completeness']:.2%}")
    print(f"Quality Metrics: {result['quality_metrics']}")
    print(f"Validation Errors: {result['validation_errors']}")
    print(f"Quality Checks: {result['quality_checks']}\n")


def example_error_handling():
    """Example: Handling malformed responses."""
    print("=== Error Handling Example ===\n")

    # Malformed keyword response (not JSON)
    llm_response = LLMResponse(
        content="키워드: Vue3, Pinia, TypeScript, Vite",
        model="gpt-4",
        finish_reason="stop",
        usage={"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}
    )

    # Postprocessor handles gracefully
    postprocessor = KeywordsPostprocessor()
    result = postprocessor.process(
        response=llm_response,
        max_keywords=10
    )

    print("Malformed Response Handling:")
    print(f"Original Response: {llm_response.content}")
    print(f"Extracted Keywords: {result['keywords']}")
    print(f"Parsing Method: {result['parsing_info']['method']}")
    print(f"Confidence: {result['confidence']:.2f}\n")


if __name__ == "__main__":
    example_summarize()
    print("\n" + "="*60 + "\n")

    example_keywords()
    print("\n" + "="*60 + "\n")

    example_normalize()
    print("\n" + "="*60 + "\n")

    example_error_handling()
