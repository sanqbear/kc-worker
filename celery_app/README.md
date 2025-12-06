# Celery Application - AI Worker Tasks

Production-grade Celery application for asynchronous AI task processing using LLM backends.

## Overview

This Celery application provides three main task types:

1. **Text Summarization** - Generate concise summaries from long text
2. **Keyword Extraction** - Extract key terms and phrases from text
3. **JSON Normalization** - Convert natural language to structured JSON

All tasks use a shared base class that handles:
- LLM API communication (llama.cpp or vLLM)
- Intelligent retry with exponential backoff
- Structured logging with correlation IDs
- Dead letter queue for failed tasks
- Graceful shutdown handling

## Architecture

```
┌─────────────┐     ┌─────────┐     ┌────────────────┐
│  Producer   │────▶│  Redis  │────▶│ Celery Worker  │
│  (API)      │     │ Broker  │     │  (Consumer)    │
└─────────────┘     └─────────┘     └────────┬───────┘
                         ▲                    │
                         │                    ▼
                         │           ┌─────────────────┐
                         └───────────│  LLM Backend    │
                          Results    │ (llama.cpp/vLLM)│
                                     └─────────────────┘
```

## Task Queues

The application uses dedicated queues for each task type:

- `summarize` - Text summarization tasks
- `keywords` - Keyword extraction tasks
- `normalize` - JSON normalization tasks
- `default` - Fallback queue

Each queue has an associated dead letter queue (DLQ) for failed tasks:

- `summarize.dlq`
- `keywords.dlq`
- `normalize.dlq`
- `default.dlq`

## Task Execution Flow

1. **Input Validation** - Validate task parameters
2. **Prompt Building** - Construct LLM prompt from inputs
3. **LLM Call** - Send request to LLM backend with retry logic
4. **Postprocessing** - Parse and validate LLM output
5. **Result Return** - Return structured result to caller

## Configuration

All configuration is loaded from environment variables (see `.env.sample`):

### Required Configuration

- `REDIS_URL` - Redis connection URL
- `LLM_SERVER_URL` - LLM inference server URL
- `LLM_BACKEND` - Backend type (`llamacpp` or `vllm`)
- `LLM_MODEL` - Model name or path

### Optional Configuration

- Task timeouts and retry settings
- Logging configuration (level, format)
- Worker concurrency settings
- LLM generation parameters (temperature, top_p, etc.)

## Usage Examples

### From Python Code

```python
from celery_app.tasks import summarize_text, extract_keywords, normalize_json

# Text summarization
result = summarize_text.delay(
    text="Long article text here...",
    max_length=150,
    language="en"
)
print(result.get())
# {
#     "summary": "Concise summary...",
#     "original_length": 500,
#     "summary_length": 145,
#     "compression_ratio": 0.29
# }

# Keyword extraction
result = extract_keywords.delay(
    text="Article about machine learning...",
    max_keywords=10,
    language="en"
)
print(result.get())
# {
#     "keywords": ["machine learning", "AI", "neural networks", ...],
#     "count": 10
# }

# JSON normalization
result = normalize_json.delay(
    request="Create a high priority ticket for login issue",
    schema={
        "properties": {
            "title": {"type": "string"},
            "priority": {"type": "string", "enum": ["low", "medium", "high"]},
            "category": {"type": "string"}
        },
        "required": ["title"]
    },
    language="en"
)
print(result.get())
# {
#     "normalized": {
#         "title": "Login issue",
#         "priority": "high",
#         "category": "authentication"
#     },
#     "confidence": 0.95
# }
```

### From Command Line (Testing)

```python
# Start Python shell
python

# Import tasks
from celery_app.tasks import summarize_text

# Submit task
result = summarize_text.delay(text="Your text here")

# Check task status
print(result.status)  # PENDING, SUCCESS, FAILURE

# Get result (blocking)
print(result.get(timeout=60))

# Get task ID
print(result.id)
```

## Reliability Features

### Automatic Retries

Tasks automatically retry on transient failures:

- Network errors
- LLM server errors (5xx)
- Timeouts

Non-retryable errors (fail immediately):

- Invalid input parameters
- LLM client errors (4xx)
- Schema validation failures

### Retry Strategy

- Maximum retries: 3 (configurable via `TASK_MAX_RETRIES`)
- Exponential backoff: 60s, 120s, 240s (base 60s)
- Jitter: ±25% to prevent thundering herd
- Maximum backoff: 1 hour

### Dead Letter Queue

Tasks that fail after all retries are sent to DLQ for manual inspection:

```bash
# Inspect DLQ
celery -A celery_app.celery inspect reserved

# Purge DLQ
celery -A celery_app.celery purge -Q summarize.dlq
```

### Graceful Shutdown

Workers handle SIGTERM/SIGINT gracefully:

1. Stop accepting new tasks
2. Complete in-flight tasks
3. Close connections cleanly
4. Exit with code 0

## Monitoring

### Celery Inspect Commands

```bash
# List active tasks
celery -A celery_app.celery inspect active

# List registered tasks
celery -A celery_app.celery inspect registered

# Get worker stats
celery -A celery_app.celery inspect stats

# Ping workers
celery -A celery_app.celery inspect ping
```

### Flower Web UI

Start Flower for web-based monitoring:

```bash
celery -A celery_app.celery flower --port=5555
```

Access at http://localhost:5555

### Logs

Logs are output in structured JSON format (production) or human-readable text (development):

```bash
# JSON logs (for log aggregation)
LOG_FORMAT=json celery -A celery_app.celery worker --loglevel=info

# Text logs (for development)
LOG_FORMAT=text celery -A celery_app.celery worker --loglevel=info
```

## Error Handling

### Error Classification

Errors are classified as retryable or non-retryable:

**Retryable Errors:**
- `LLMServerError` - 5xx errors from LLM server
- `LLMTimeoutError` - Request timeout
- `RateLimitError` - 429 rate limit
- `ConnectionError` - Network errors

**Non-Retryable Errors:**
- `InvalidInputError` - Bad task parameters
- `LLMClientError` - 4xx errors from LLM server
- `AuthenticationError` - 401/403 errors
- `SchemaValidationError` - Output doesn't match schema

### Custom Error Handling

To add custom error handling, subclass `BaseLLMTask` and override `on_failure`:

```python
class CustomTask(BaseLLMTask):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        super().on_failure(exc, task_id, args, kwargs, einfo)
        # Add custom logic (e.g., send alert, log to external service)
```

## Performance Tuning

### Worker Concurrency

Number of parallel tasks per worker:

```bash
# 4 concurrent tasks (default)
celery -A celery_app.celery worker --concurrency=4

# Auto-scale based on load (min 2, max 10)
celery -A celery_app.celery worker --autoscale=10,2
```

### Prefetch Multiplier

Number of tasks to fetch per worker (1 = fair scheduling):

```bash
# Fair scheduling (recommended for long tasks)
celery -A celery_app.celery worker --prefetch-multiplier=1

# Batch prefetch (for short tasks)
celery -A celery_app.celery worker --prefetch-multiplier=4
```

### Task Routing

Route tasks to specific workers:

```bash
# Worker for summarization only
celery -A celery_app.celery worker -Q summarize

# Worker for keywords only
celery -A celery_app.celery worker -Q keywords

# Worker for all queues
celery -A celery_app.celery worker -Q summarize,keywords,normalize
```

## Development

### Adding New Tasks

1. Create task class inheriting from `BaseLLMTask`
2. Implement `build_prompt()` method
3. Implement `postprocess()` method
4. Decorate with `@app.task()`
5. Register in `celery_app/tasks/__init__.py`

Example:

```python
from celery_app.tasks.base import BaseLLMTask
from celery_app.celery import app

class TranslateTask(BaseLLMTask):
    name = "celery_app.tasks.translate.translate_text"

    def build_prompt(self, **kwargs):
        text = kwargs["text"]
        target_lang = kwargs["target_lang"]
        return f"Translate to {target_lang}: {text}"

    def postprocess(self, llm_output, **kwargs):
        return {"translation": llm_output.strip()}

@app.task(bind=True, base=TranslateTask)
def translate_text(self, **kwargs):
    return self.run(**kwargs)
```

### Testing

Run tests with pytest:

```bash
# All tests
pytest tests/

# Specific test file
pytest tests/test_tasks.py

# With coverage
pytest --cov=celery_app tests/
```

## Troubleshooting

### Task Stuck in PENDING

- Check if worker is running: `celery -A celery_app.celery inspect active`
- Check Redis connection: `redis-cli ping`
- Check task routing: ensure task is routed to correct queue

### Task Timeout

- Increase `TASK_SOFT_TIME_LIMIT` and `TASK_TIME_LIMIT`
- Check LLM server performance
- Reduce `MAX_TOKENS` for faster generation

### High Memory Usage

- Reduce `WORKER_CONCURRENCY`
- Enable worker max tasks per child: `--max-tasks-per-child=1000`
- Check for memory leaks in custom code

### Failed Tasks Not Retrying

- Check exception type (non-retryable errors don't retry)
- Check `TASK_MAX_RETRIES` setting
- Review logs for retry attempts

## Production Deployment

### Systemd Service

Create `/etc/systemd/system/celery-worker.service`:

```ini
[Unit]
Description=Celery Worker
After=network.target redis.service

[Service]
Type=forking
User=celery
Group=celery
WorkingDirectory=/opt/worker
Environment="PATH=/opt/worker/venv/bin"
ExecStart=/opt/worker/venv/bin/celery -A celery_app.celery worker \
          --loglevel=info \
          --concurrency=4 \
          --max-tasks-per-child=1000 \
          --time-limit=300
Restart=always

[Install]
WantedBy=multi-user.target
```

### Docker Deployment

See `docker-compose.yml` in parent directory for containerized deployment.

### Kubernetes Deployment

Use Celery Executor with horizontal pod autoscaling:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: celery-worker
spec:
  replicas: 3
  selector:
    matchLabels:
      app: celery-worker
  template:
    metadata:
      labels:
        app: celery-worker
    spec:
      containers:
      - name: worker
        image: knowledgecenter/worker:latest
        command: ["celery", "-A", "celery_app.celery", "worker"]
        env:
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: redis-secret
              key: url
```

## Security Considerations

1. **Redis Authentication**: Use password-protected Redis in production
2. **TLS/SSL**: Use `rediss://` for encrypted Redis connections
3. **Task Serialization**: Only use JSON serializer (no pickle)
4. **Input Validation**: All task inputs are validated before processing
5. **Resource Limits**: Task time limits prevent infinite loops
6. **Network Isolation**: Run workers in isolated network namespace

## License

Part of the Knowledge Center project.
