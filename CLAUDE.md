# CLAUDE.md

This file provides guidance to Claude Code when working with the worker service.

## Project Overview

Python AI Worker service that processes AI tasks (summarization, keyword extraction, JSON normalization) using Celery with Redis as message broker. Supports both llama.cpp and vLLM backends for LLM inference.

## Setup

```bash
# Windows
setup_venv.bat

# Linux/macOS
chmod +x setup_venv.sh
./setup_venv.sh
```

## Common Commands

```bash
# Activate virtual environment
# Windows:
venv\Scripts\activate.bat
# Linux/macOS:
source venv/bin/activate

# Start Redis (Docker)
docker-compose up -d redis

# Start LLM server (choose one)
docker-compose -f docker-compose.yml -f docker-compose.llamacpp.yml up -d llm-server
# or
docker-compose -f docker-compose.yml -f docker-compose.vllm.yml up -d llm-server

# Start Celery worker
celery -A celery_app.celery worker --loglevel=info

# Run tests
pytest tests/

# Check Celery worker status
celery -A celery_app.celery inspect active
```

## Architecture

```
┌─────────────┐     ┌─────────┐     ┌────────────────┐     ┌─────────────────────┐
│  Go API     │────▶│  Redis  │────▶│ Celery Worker  │────▶│ LLM Backend         │
│  Server     │◀────│ (Docker)│◀────│ (venv/Python)  │◀────│ (llama.cpp / vLLM)  │
└─────────────┘     └─────────┘     └────────────────┘     └─────────────────────┘
```

## Directory Structure

```
worker/
├── celery_app/           # Celery application
│   ├── celery.py         # Celery app initialization
│   ├── config.py         # Settings from environment
│   └── tasks/            # Task implementations
│       ├── base.py       # Base task class
│       ├── summarize.py  # Summarization task
│       ├── keywords.py   # Keyword extraction task
│       └── normalize.py  # JSON normalization task
│
├── llm/                  # LLM client abstraction
│   ├── base.py           # Abstract base class
│   ├── factory.py        # Client factory
│   ├── llamacpp_client.py
│   ├── vllm_client.py
│   ├── response.py       # Response models
│   └── prompts/          # Prompt templates
│
├── postprocess/          # Result postprocessors
│
├── models/               # LLM models (gitignored)
│   ├── gguf/             # GGUF models for llama.cpp
│   └── hf/               # HuggingFace models for vLLM
│
└── tests/                # Test files
```

## Task Types

1. **Summarize**: Text summarization
   - Input: `{"text": "...", "max_length": 200}`
   - Output: `{"summary": "...", "original_length": N, "summary_length": N}`

2. **Keywords**: Keyword extraction
   - Input: `{"text": "...", "max_keywords": 10}`
   - Output: `{"keywords": ["..."], "count": N}`

3. **Normalize**: Natural language to JSON
   - Input: `{"request": "...", "schema": {...}}`
   - Output: `{"normalized": {...}, "confidence": 0.9}`

## Environment Variables

Copy `.env.sample` to `.env` and configure:
- `REDIS_URL` - Redis connection string
- `LLM_SERVER_URL` - LLM server URL
- `LLM_BACKEND` - "llamacpp" or "vllm"
- `LLM_MODEL` - Model name/path

## LLM Models

### GGUF (llama.cpp)
Place models in `models/gguf/`:
- `llama-3-Korean-Bllossom-8B-Q4_K_M.GGUF` (fast)
- `llama-3-Korean-Bllossom-8B-Q8.GGUF` (quality)

### Safetensors (vLLM)
Place models in `models/hf/`

## Adding New Tasks

1. Create prompt template in `llm/prompts/`
2. Create postprocessor in `postprocess/`
3. Create task in `celery_app/tasks/`
4. Register task in `celery_app/tasks/__init__.py`
