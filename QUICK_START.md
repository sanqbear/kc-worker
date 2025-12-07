# Quick Start Guide - Celery Worker

Fast setup guide for the Knowledge Center AI Worker service.

## Prerequisites

- Python 3.11+
- Redis server (via Docker or standalone)
- LLM server (llama.cpp or vLLM)

## 5-Minute Setup

### 1. Create Virtual Environment

**Windows**:
```bash
cd 
python -m venv venv
venv\Scripts\activate.bat
```

**Linux/macOS**:
```bash
cd /path/to/knowledgecenter/worker
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
# Copy sample config
cp .env.sample .env

# Edit .env (minimal configuration)
# Required:
# REDIS_URL=redis://localhost:6379/0
# LLM_SERVER_URL=http://localhost:8000
# LLM_BACKEND=llamacpp
```

### 4. Start Redis (Docker)

```bash
cd ..  # Go to project root
docker-compose up -d redis
```

### 5. Start Worker

**Windows**:
```bash
cd worker
start_worker.bat
```

**Linux/macOS**:
```bash
cd worker
chmod +x start_worker.sh
./start_worker.sh
```

You should see:
```
[2025-12-06 21:00:00,000: INFO/MainProcess] Connected to redis://localhost:6379/0
[2025-12-06 21:00:00,100: INFO/MainProcess] mingle: searching for neighbors
[2025-12-06 21:00:01,200: INFO/MainProcess] celery@hostname ready.
```

## Test the Worker

### Python Shell Test

```bash
# In worker directory with venv activated
python
```

```python
from celery_app.tasks import summarize_text

# Submit task
result = summarize_text.delay(
    text="Machine learning is a subset of artificial intelligence that enables computers to learn from data without explicit programming.",
    max_length=50
)

# Check status
print(result.status)  # PENDING, then SUCCESS

# Get result (blocking)
output = result.get(timeout=60)
print(output)
# {
#     'summary': 'Machine learning is AI that allows computers to learn from data.',
#     'original_length': 20,
#     'summary_length': 11,
#     'compression_ratio': 0.55
# }
```

### Command Line Test

```bash
# Submit task
celery -A celery_app.celery call celery_app.tasks.summarize.summarize_text \
  --kwargs='{"text": "Test text", "max_length": 50}'

# List active tasks
celery -A celery_app.celery inspect active

# Get worker stats
celery -A celery_app.celery inspect stats
```

## Common Tasks

### Start Flower Monitoring UI

```bash
celery -A celery_app.celery flower --port=5555
# Open http://localhost:5555
```

### Check Health

```bash
# Basic health
curl http://localhost:8001/health

# Readiness (is worker accepting tasks?)
curl http://localhost:8001/health/ready

# Metrics
curl http://localhost:8001/metrics
```

### View Logs

Logs are printed to stdout in JSON format (production) or text format (development).

Change format:
```bash
# In .env
LOG_FORMAT=text  # for development
LOG_FORMAT=json  # for production
```

### Stop Worker

Press `Ctrl+C` once - the worker will complete current tasks and shutdown gracefully.

## Directory Structure

```
worker/
├── celery_app/           # Main application
│   ├── celery.py         # Celery app initialization
│   ├── config.py         # Configuration
│   ├── tasks/            # Task definitions
│   │   ├── base.py       # Base task class
│   │   ├── summarize.py  # Summarization
│   │   ├── keywords.py   # Keyword extraction
│   │   └── normalize.py  # JSON normalization
│   └── utils/            # Utilities
│       ├── logging.py    # Structured logging
│       └── retry.py      # Retry logic
│
├── .env                  # Your configuration (not in git)
├── .env.sample           # Configuration template
├── requirements.txt      # Python dependencies
├── start_worker.bat      # Windows startup script
└── start_worker.sh       # Linux/macOS startup script
```

## Available Tasks

### 1. Summarize Text

```python
from celery_app.tasks import summarize_text

summarize_text.delay(
    text="Long text here...",
    max_length=200,  # Optional, default: 200
    language="en"    # Optional, default: "auto"
)
```

### 2. Extract Keywords

```python
from celery_app.tasks import extract_keywords

extract_keywords.delay(
    text="Article text...",
    max_keywords=10,  # Optional, default: 10
    language="en"     # Optional, default: "auto"
)
```

### 3. Normalize JSON

```python
from celery_app.tasks import normalize_json

normalize_json.delay(
    request="Create high priority ticket for login issue",
    schema={
        "properties": {
            "title": {"type": "string"},
            "priority": {"type": "string"}
        },
        "required": ["title"]
    },
    language="en"  # Optional, default: "auto"
)
```

## Troubleshooting

### Worker Won't Start

1. **Check Redis connection**:
   ```bash
   redis-cli ping
   # Should return: PONG
   ```

2. **Check venv is activated**:
   ```bash
   which python  # Should point to venv/bin/python
   ```

3. **Check .env file exists**:
   ```bash
   ls -la .env
   ```

### Tasks Stay PENDING

1. **Check worker is running**:
   ```bash
   celery -A celery_app.celery inspect active
   ```

2. **Check task routing** - ensure task name matches registered name

3. **Check Redis connection from worker logs**

### LLM Errors

1. **Check LLM server is running**:
   ```bash
   curl http://localhost:8000/health  # or appropriate endpoint
   ```

2. **Check LLM_SERVER_URL in .env**

3. **Check LLM_BACKEND matches your server** (llamacpp vs vllm)

### Import Errors

```bash
# Reinstall dependencies
pip install --upgrade -r requirements.txt
```

## Next Steps

1. Read [CELERY_IMPLEMENTATION.md](CELERY_IMPLEMENTATION.md) for full documentation
2. Read [INTEGRATION_EXAMPLE.md](INTEGRATION_EXAMPLE.md) for Go API integration
3. Check [celery_app/README.md](celery_app/README.md) for detailed task documentation

## Production Deployment

For production deployment see:
- Systemd service configuration in [CELERY_IMPLEMENTATION.md](CELERY_IMPLEMENTATION.md)
- Docker deployment in root `docker-compose.yml`
- Kubernetes deployment examples in documentation

## Getting Help

1. Check logs for error messages
2. Review configuration in `.env`
3. Test Redis connection: `redis-cli ping`
4. Test LLM server: `curl http://localhost:8000`
5. Check worker status: `celery -A celery_app.celery inspect stats`

## Summary

You now have a running Celery worker that can process AI tasks! Submit tasks using the Python API or integrate with the Go backend following [INTEGRATION_EXAMPLE.md](INTEGRATION_EXAMPLE.md).
