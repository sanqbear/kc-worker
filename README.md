# Knowledge Center AI Worker

Python-based asynchronous worker service for AI-powered background tasks in the Knowledge Center application.

## Architecture

- **Task Queue**: Redis with Celery/ARQ for reliable task distribution
- **LLM Backends**:
  - llama.cpp (GGUF models) - CPU/GPU inference
  - vLLM (SafeTensors models) - GPU-optimized inference
- **Worker Pattern**: Async workers with graceful shutdown and fault tolerance

## Directory Structure

```
worker/
├── models/                      # Model storage (gitignored)
│   ├── gguf/                   # GGUF models for llama.cpp
│   └── hf/                     # HuggingFace models for vLLM
├── docker-compose.yml          # Base: Redis only
├── docker-compose.llamacpp.yml # llama.cpp server override
├── docker-compose.vllm.yml     # vLLM server override
├── Dockerfile.llamacpp         # llama.cpp server image
├── Dockerfile.vllm             # vLLM server image
├── .env.sample                 # Environment template
└── .gitignore                  # Ignore venv, models, etc.
```

## Quick Start

### 1. Setup Python Environment (Local Development)

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
.\venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate

# Install dependencies (to be created)
pip install -r requirements.txt
```

### 2. Start Redis Only

```bash
# Copy environment file
cp .env.sample .env

# Start Redis
docker-compose up -d

# Check Redis health
docker-compose ps
```

### 3. Start with llama.cpp Backend

```bash
# Download a GGUF model to ./models/gguf/
# Example: Download from HuggingFace
# Place model at ./models/gguf/model.gguf

# Configure .env
# MODEL_PATH=/models/model.gguf
# N_GPU_LAYERS=0  # CPU-only, or -1 for full GPU

# Start Redis + llama.cpp server
docker-compose -f docker-compose.yml -f docker-compose.llamacpp.yml up -d

# Check logs
docker-compose logs -f llm-server

# Test API
curl http://localhost:8000/v1/models
```

### 4. Start with vLLM Backend

```bash
# Download a HuggingFace model to ./models/hf/
# Example: Use huggingface-cli
# huggingface-cli download --repo-type model --local-dir ./models/hf/model <model-name>

# Configure .env
# MODEL_NAME=/models/model
# TENSOR_PARALLEL_SIZE=1
# GPU_MEMORY_UTILIZATION=0.9

# Start Redis + vLLM server
docker-compose -f docker-compose.yml -f docker-compose.vllm.yml up -d

# Check logs
docker-compose logs -f llm-server

# Test API
curl http://localhost:8000/v1/models
```

## Development Workflow

### Local Worker Development

Workers run locally using Python venv (NOT in Docker):

```bash
# Activate venv
source venv/bin/activate  # or .\venv\Scripts\activate on Windows

# Run worker (to be implemented)
python -m worker.main

# Or use auto-reload during development
watchmedo auto-restart -d . -p '*.py' -- python -m worker.main
```

### Docker Services

Only infrastructure runs in Docker:
- Redis (message broker)
- LLM server (llama.cpp or vLLM)

### Switching LLM Backends

```bash
# Stop current setup
docker-compose down

# Start with different backend
docker-compose -f docker-compose.yml -f docker-compose.llamacpp.yml up -d
# OR
docker-compose -f docker-compose.yml -f docker-compose.vllm.yml up -d
```

## Model Management

### GGUF Models (llama.cpp)

Place models in `./models/gguf/`:

```bash
# Example: Download from HuggingFace
wget https://huggingface.co/.../model.gguf -O ./models/gguf/model.gguf

# Update .env
MODEL_PATH=/models/model.gguf
```

### HuggingFace Models (vLLM)

Place models in `./models/hf/`:

```bash
# Using huggingface-cli
pip install huggingface-hub
huggingface-cli download --repo-type model --local-dir ./models/hf/llama-model meta-llama/Llama-2-7b-chat-hf

# Update .env
MODEL_NAME=/models/llama-model
```

## Environment Variables

See `.env.sample` for all configuration options:

- **Redis**: Connection settings
- **LLM Server**: URL and timeout
- **llama.cpp**: Model path, context size, GPU layers
- **vLLM**: Model name, tensor parallelism, GPU memory
- **Worker**: Concurrency, retries, timeouts

## Health Checks

### Redis
```bash
docker-compose exec redis redis-cli ping
# Expected: PONG
```

### LLM Server
```bash
curl http://localhost:8000/health
# Expected: {"status":"ok"}
```

### Worker (to be implemented)
```bash
curl http://localhost:8001/health
# Expected: {"status":"healthy","redis":"connected","llm":"connected"}
```

## Deployment Considerations

### GPU Support

Both Dockerfiles support NVIDIA GPUs:

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: all
          capabilities: [gpu]
```

Ensure `nvidia-docker` is installed on the host.

### Scaling Workers

Workers are stateless and can be scaled horizontally:

```bash
# Run multiple worker instances
python -m worker.main &
python -m worker.main &
python -m worker.main &
```

Or use process managers like systemd, supervisor, or Kubernetes.

### Production Checklist

- [ ] Set strong Redis password
- [ ] Configure proper resource limits (CPU, memory, GPU)
- [ ] Enable structured logging with correlation IDs
- [ ] Set up monitoring (Prometheus metrics)
- [ ] Configure dead letter queue for failed tasks
- [ ] Implement graceful shutdown (SIGTERM handling)
- [ ] Set up distributed tracing (OpenTelemetry)
- [ ] Use secrets management (not .env files)

## Troubleshooting

### llama.cpp fails to start

Check model path and file exists:
```bash
docker-compose exec llm-server ls -lh /models/
```

### vLLM out of memory

Reduce GPU memory utilization:
```bash
GPU_MEMORY_UTILIZATION=0.7
```

Or reduce max model length:
```bash
MAX_MODEL_LEN=2048
```

### Redis connection refused

Ensure Redis is running:
```bash
docker-compose ps redis
docker-compose logs redis
```

## Next Steps

1. Implement worker core (`worker/main.py`)
2. Define task processors (`worker/tasks/`)
3. Add health check endpoints
4. Implement retry logic with exponential backoff
5. Add structured logging
6. Create unit and integration tests
7. Set up CI/CD pipeline

## License

See parent project LICENSE file.
