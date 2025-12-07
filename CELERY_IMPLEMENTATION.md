# Celery Application Implementation Summary

## Overview

A production-grade Celery application for asynchronous AI task processing has been implemented in `\celery_app\`. This implementation follows enterprise-level reliability patterns and best practices for background processing systems.

## Architecture

### Technology Stack

- **Message Broker**: Redis (both broker and result backend)
- **Task Queue**: Celery 5.4.0 with JSON serialization
- **HTTP Client**: aiohttp for async LLM API calls
- **Configuration**: Pydantic Settings with environment-based config
- **Logging**: Structlog with JSON/text output formats
- **LLM Backends**: Supports both llama.cpp and vLLM

### Directory Structure

```
celery_app/
├── __init__.py           # Package initialization
├── celery.py             # Celery app initialization, queues, routing
├── config.py             # Pydantic settings from environment
├── health.py             # Health check HTTP server (liveness/readiness)
├── main.py               # Main entry point
├── README.md             # Comprehensive documentation
│
├── tasks/
│   ├── __init__.py       # Task exports
│   ├── base.py           # BaseLLMTask abstract class
│   ├── summarize.py      # Text summarization task
│   ├── keywords.py       # Keyword extraction task
│   └── normalize.py      # JSON normalization task
│
└── utils/
    ├── __init__.py       # Utility exports
    ├── logging.py        # Structured logging setup
    └── retry.py          # Retry logic and error classification
```

## Implemented Tasks

### 1. Text Summarization (summarize_text)

**Queue**: `summarize`

**Input**:
```python
{
    "text": "Long article text here...",
    "max_length": 200,       # Optional, default: 200
    "language": "en"         # Optional, default: "auto"
}
```

**Output**:
```python
{
    "summary": "Concise summary...",
    "original_length": 500,
    "summary_length": 145,
    "compression_ratio": 0.29
}
```

**Features**:
- Supports both English and Korean
- Configurable summary length
- Calculates compression metrics

### 2. Keyword Extraction (extract_keywords)

**Queue**: `keywords`

**Input**:
```python
{
    "text": "Article text...",
    "max_keywords": 10,      # Optional, default: 10
    "language": "en"         # Optional, default: "auto"
}
```

**Output**:
```python
{
    "keywords": ["keyword1", "keyword2", ...],
    "count": 10
}
```

**Features**:
- JSON array extraction from LLM output
- Automatic deduplication
- Fallback to text splitting if JSON parsing fails

### 3. JSON Normalization (normalize_json)

**Queue**: `normalize`

**Input**:
```python
{
    "request": "Create high priority ticket for login issue",
    "schema": {
        "properties": {
            "title": {"type": "string"},
            "priority": {"type": "string", "enum": ["low", "medium", "high"]},
            "category": {"type": "string"}
        },
        "required": ["title"]
    },
    "examples": [            # Optional, for few-shot learning
        {
            "input": "Example request",
            "output": {"title": "Example", "priority": "low"}
        }
    ],
    "language": "en"         # Optional, default: "auto"
}
```

**Output**:
```python
{
    "normalized": {
        "title": "Login issue",
        "priority": "high",
        "category": "authentication"
    },
    "confidence": 0.95
}
```

**Features**:
- Schema validation with required field checking
- Confidence scoring based on field completeness
- Few-shot learning support via examples

## Core Features

### Reliability Patterns

1. **Automatic Retries with Exponential Backoff**
   - Base delay: 60 seconds
   - Exponential multiplier: 2x
   - Maximum retries: 3 (configurable)
   - Jitter: ±25% to prevent thundering herd

2. **Error Classification**
   - **Retryable Errors**: LLM server errors (5xx), timeouts, network errors, rate limits
   - **Non-Retryable Errors**: Invalid input, client errors (4xx), schema validation failures

3. **Dead Letter Queues**
   - Separate DLQ for each task queue
   - Tasks sent to DLQ after max retries exhausted
   - Queues: `summarize.dlq`, `keywords.dlq`, `normalize.dlq`, `default.dlq`

4. **Graceful Shutdown**
   - SIGTERM/SIGINT signal handlers
   - Complete in-flight tasks before shutdown
   - Clean connection closure

5. **Task Idempotency**
   - Tasks designed to be safely re-executed
   - No side effects from multiple executions
   - Safe for retry scenarios

### Configuration Management

All configuration via environment variables (see `.env.sample`):

**Redis**:
- `REDIS_URL` - Connection URL

**LLM Server**:
- `LLM_SERVER_URL` - Base URL
- `LLM_BACKEND` - "llamacpp" or "vllm"
- `LLM_MODEL` - Model name/path

**Task Settings**:
- `TASK_SOFT_TIME_LIMIT` - Soft timeout (default: 180s)
- `TASK_TIME_LIMIT` - Hard timeout (default: 300s)
- `TASK_MAX_RETRIES` - Max retries (default: 3)
- `TASK_RETRY_DELAY` - Initial retry delay (default: 60s)

**Worker Settings**:
- `WORKER_CONCURRENCY` - Concurrent tasks (default: 4)
- `WORKER_PREFETCH_MULTIPLIER` - Task prefetch (default: 1)

**Logging**:
- `LOG_LEVEL` - DEBUG/INFO/WARNING/ERROR/CRITICAL
- `LOG_FORMAT` - "json" (production) or "text" (development)

**Health Checks**:
- `HEALTH_CHECK_ENABLED` - Enable HTTP server (default: true)
- `HEALTH_CHECK_PORT` - Port for health server (default: 8001)

### Logging and Observability

1. **Structured Logging**
   - JSON format for production (log aggregation)
   - Human-readable text for development
   - Correlation IDs for request tracing
   - Automatic task context binding

2. **Health Check Endpoints**
   - `GET /health` - Basic health status
   - `GET /health/live` - Liveness probe (process alive)
   - `GET /health/ready` - Readiness probe (ready for tasks)
   - `GET /metrics` - Worker and task metrics

3. **Task Monitoring**
   - Task state tracking (PENDING, SUCCESS, FAILURE)
   - Task events enabled for real-time monitoring
   - Flower UI support for web-based monitoring

### Base Task Class (BaseLLMTask)

All tasks inherit from `BaseLLMTask` which provides:

**Template Method Pattern**:
```
1. build_prompt(**kwargs) → str
2. call_llm(prompt) → str
3. postprocess(llm_output, **kwargs) → Dict[str, Any]
```

**Features**:
- Automatic session management for HTTP client
- LLM backend abstraction (llama.cpp vs vLLM)
- Retry logic integration
- Structured logging with task context
- Error handling and classification

**Abstract Methods** (must be implemented by subclasses):
- `build_prompt(**kwargs)` - Construct LLM prompt from inputs
- `postprocess(llm_output, **kwargs)` - Parse and validate LLM output

## Usage

### Starting the Worker

**Windows**:
```bash
# Activate virtual environment
venv\Scripts\activate.bat

# Start worker
start_worker.bat

# Or manually:
celery -A celery_app.celery worker --loglevel=info --concurrency=4
```

**Linux/macOS**:
```bash
# Activate virtual environment
source venv/bin/activate

# Start worker
chmod +x start_worker.sh
./start_worker.sh

# Or manually:
celery -A celery_app.celery worker --loglevel=info --concurrency=4
```

### Submitting Tasks from Python

```python
from celery_app.tasks import summarize_text, extract_keywords, normalize_json

# Summarize text
result = summarize_text.delay(
    text="Long article about machine learning and AI systems...",
    max_length=150
)

# Wait for result (blocking)
summary = result.get(timeout=60)
print(summary)
# {
#     "summary": "This article discusses...",
#     "original_length": 45,
#     "summary_length": 12,
#     "compression_ratio": 0.27
# }

# Extract keywords (async)
result = extract_keywords.delay(
    text="Article about machine learning...",
    max_keywords=5
)
# Check status later
print(result.status)  # PENDING, SUCCESS, FAILURE

# Normalize natural language to JSON
result = normalize_json.delay(
    request="한글로 작성된 긴급 티켓 생성",
    schema={
        "properties": {
            "title": {"type": "string"},
            "priority": {"type": "string"}
        },
        "required": ["title"]
    },
    language="ko"
)
normalized = result.get()
print(normalized["normalized"])
```

### Monitoring Tasks

```bash
# List active tasks
celery -A celery_app.celery inspect active

# List registered tasks
celery -A celery_app.celery inspect registered

# Get worker stats
celery -A celery_app.celery inspect stats

# Ping workers
celery -A celery_app.celery inspect ping

# Start Flower web UI
celery -A celery_app.celery flower --port=5555
# Access at http://localhost:5555
```

### Health Checks

```bash
# Check health
curl http://localhost:8001/health

# Check liveness
curl http://localhost:8001/health/live

# Check readiness
curl http://localhost:8001/health/ready

# Get metrics
curl http://localhost:8001/metrics
```

## Integration with Go API Server

The Go API server can submit tasks to the worker:

```go
package main

import (
    "context"
    "encoding/json"
    "fmt"

    "github.com/go-redis/redis/v8"
)

type SummarizeTask struct {
    Text      string `json:"text"`
    MaxLength int    `json:"max_length"`
    Language  string `json:"language"`
}

func submitSummarizeTask(rdb *redis.Client, text string) (string, error) {
    ctx := context.Background()

    task := SummarizeTask{
        Text:      text,
        MaxLength: 200,
        Language:  "en",
    }

    taskJSON, _ := json.Marshal(task)

    // Create Celery task message
    message := map[string]interface{}{
        "task": "celery_app.tasks.summarize.summarize_text",
        "id":   "unique-task-id",
        "args": []interface{}{},
        "kwargs": task,
    }

    messageJSON, _ := json.Marshal(message)

    // Push to Redis queue
    err := rdb.LPush(ctx, "summarize", messageJSON).Err()
    if err != nil {
        return "", err
    }

    return "unique-task-id", nil
}
```

## Production Deployment

### Systemd Service

Create `/etc/systemd/system/celery-worker.service`:

```ini
[Unit]
Description=Celery Worker for Knowledge Center
After=network.target redis.service

[Service]
Type=forking
User=celery
Group=celery
WorkingDirectory=/opt/knowledgecenter/worker
Environment="PATH=/opt/knowledgecenter/worker/venv/bin"
EnvironmentFile=/opt/knowledgecenter/worker/.env

ExecStart=/opt/knowledgecenter/worker/venv/bin/celery \
          -A celery_app.celery worker \
          --loglevel=info \
          --concurrency=4 \
          --max-tasks-per-child=1000 \
          --pidfile=/var/run/celery/worker.pid \
          --logfile=/var/log/celery/worker.log

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Docker Deployment

See `docker-compose.yml` in parent directory.

### Scaling

**Horizontal Scaling**:
```bash
# Start multiple workers
celery -A celery_app.celery worker -n worker1@%h -c 4
celery -A celery_app.celery worker -n worker2@%h -c 4
celery -A celery_app.celery worker -n worker3@%h -c 4
```

**Queue-Specific Workers**:
```bash
# Worker for summarization only
celery -A celery_app.celery worker -Q summarize -c 8

# Worker for keywords only
celery -A celery_app.celery worker -Q keywords -c 4

# General worker for all queues
celery -A celery_app.celery worker -Q summarize,keywords,normalize -c 4
```

## Testing

Run tests with pytest:

```bash
# Activate venv
source venv/bin/activate  # or venv\Scripts\activate.bat on Windows

# Install test dependencies
pip install -r requirements.txt

# Run all tests
pytest tests/

# Run with coverage
pytest --cov=celery_app tests/

# Run specific test file
pytest tests/test_tasks.py

# Run with verbose output
pytest -v tests/
```

## Files Created

### Core Files

1. `celery_app/__init__.py` - Package initialization
2. `celery_app/celery.py` - Celery app with queues and routing
3. `celery_app/config.py` - Pydantic settings configuration
4. `celery_app/health.py` - Health check HTTP server
5. `celery_app/main.py` - Main entry point

### Task Files

6. `celery_app/tasks/__init__.py` - Task exports
7. `celery_app/tasks/base.py` - BaseLLMTask abstract class
8. `celery_app/tasks/summarize.py` - Summarization task
9. `celery_app/tasks/keywords.py` - Keyword extraction task
10. `celery_app/tasks/normalize.py` - JSON normalization task

### Utility Files

11. `celery_app/utils/__init__.py` - Utility exports
12. `celery_app/utils/logging.py` - Structured logging
13. `celery_app/utils/retry.py` - Retry logic and error classification

### Documentation and Configuration

14. `celery_app/README.md` - Comprehensive documentation
15. `.env.sample` - Environment configuration template
16. `requirements.txt` - Python dependencies
17. `start_worker.bat` - Windows startup script
18. `start_worker.sh` - Linux/macOS startup script

## Next Steps

1. **Configure Environment**: Copy `.env.sample` to `.env` and configure settings
2. **Install Dependencies**: `pip install -r requirements.txt`
3. **Start Redis**: `docker-compose up -d redis` (or use existing Redis)
4. **Start LLM Server**: Start llama.cpp or vLLM backend
5. **Start Worker**: `./start_worker.sh` or `start_worker.bat`
6. **Test Tasks**: Submit test tasks from Python shell
7. **Monitor**: Use Flower UI or Celery inspect commands
8. **Integrate**: Add task submission from Go API server

## Key Design Decisions

1. **Redis as Broker**: Simple, fast, no additional dependencies
2. **JSON Serialization**: Cross-language compatibility, no pickle security issues
3. **Async HTTP Client**: aiohttp for non-blocking LLM API calls
4. **Structured Logging**: JSON logs for production log aggregation
5. **Dead Letter Queues**: Automatic failure handling without data loss
6. **Fair Scheduling**: Prefetch multiplier of 1 for long-running tasks
7. **Task Time Limits**: Prevent infinite loops and resource exhaustion
8. **Health Checks**: Kubernetes/Docker orchestration compatibility

## Summary

This implementation provides a robust, production-ready Celery worker service for AI task processing with comprehensive error handling, monitoring, and reliability features. All tasks follow a consistent pattern using the `BaseLLMTask` abstract class, making it easy to add new task types in the future.
