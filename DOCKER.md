# Docker Infrastructure Documentation

This document describes the Docker infrastructure for the Knowledge Center AI Worker service.

## Overview

The worker service uses a hybrid deployment model:
- **Infrastructure** (Redis, LLM servers) runs in Docker containers
- **Worker processes** run locally using Python venv for faster development iteration

## File Structure

```
worker/
├── docker-compose.yml              # Base: Redis only
├── docker-compose.llamacpp.yml     # Override: Add llama.cpp server
├── docker-compose.vllm.yml         # Override: Add vLLM server
├── Dockerfile.llamacpp             # llama.cpp server image
├── Dockerfile.vllm                 # vLLM server image
├── .env.sample                     # Environment template
├── .gitignore                      # Git ignore patterns
└── models/                         # Model storage
    ├── .gitkeep
    ├── gguf/                       # GGUF models for llama.cpp
    │   └── .gitkeep
    └── hf/                         # HuggingFace models for vLLM
        └── .gitkeep
```

## Docker Compose Files

### Base Configuration (docker-compose.yml)

**Services:**
- `redis`: Redis 7 Alpine
  - Port: 6379
  - Persistent volume: `redis-data`
  - AOF persistence enabled
  - Health check: `redis-cli ping`
  - Network: `worker-network`

**Usage:**
```bash
# Start Redis only
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f redis

# Stop
docker-compose down
```

### llama.cpp Override (docker-compose.llamacpp.yml)

**Additional Service:**
- `llm-server`: llama.cpp OpenAI-compatible API
  - Port: 8000
  - Volume: `./models/gguf:/models:ro` (read-only)
  - GPU support: NVIDIA (optional)
  - Health check: `curl http://localhost:8000/health`

**Environment Variables:**
- `MODEL_PATH`: Path to GGUF model file (default: `/models/model.gguf`)
- `N_CTX`: Context window size (default: `4096`)
- `N_GPU_LAYERS`: Number of layers to offload to GPU (default: `0` for CPU-only)
- `HOST`: Bind address (default: `0.0.0.0`)
- `PORT`: Server port (default: `8000`)

**Usage:**
```bash
# Start Redis + llama.cpp
docker-compose -f docker-compose.yml -f docker-compose.llamacpp.yml up -d

# Build and start
docker-compose -f docker-compose.yml -f docker-compose.llamacpp.yml up --build -d

# View llm-server logs
docker-compose logs -f llm-server

# Test API
curl http://localhost:8000/v1/models
curl http://localhost:8000/health

# Stop all services
docker-compose -f docker-compose.yml -f docker-compose.llamacpp.yml down
```

### vLLM Override (docker-compose.vllm.yml)

**Additional Service:**
- `llm-server`: vLLM OpenAI-compatible API
  - Port: 8000
  - Volume: `./models/hf:/models:ro` (read-only)
  - GPU support: NVIDIA (required)
  - Shared memory: 16GB
  - Health check: `curl http://localhost:8000/health`

**Environment Variables:**
- `MODEL_NAME`: HuggingFace model path (default: `/models/model`)
- `TENSOR_PARALLEL_SIZE`: Number of GPUs for tensor parallelism (default: `1`)
- `GPU_MEMORY_UTILIZATION`: GPU memory fraction (default: `0.9`)
- `MAX_MODEL_LEN`: Maximum sequence length (default: `4096`)
- `HOST`: Bind address (default: `0.0.0.0`)
- `PORT`: Server port (default: `8000`)

**Usage:**
```bash
# Start Redis + vLLM
docker-compose -f docker-compose.yml -f docker-compose.vllm.yml up -d

# Build and start
docker-compose -f docker-compose.yml -f docker-compose.vllm.yml up --build -d

# View llm-server logs
docker-compose logs -f llm-server

# Test API
curl http://localhost:8000/v1/models
curl http://localhost:8000/health

# Stop all services
docker-compose -f docker-compose.yml -f docker-compose.vllm.yml down
```

## Dockerfiles

### Dockerfile.llamacpp

**Base Image:** `python:3.11-slim`

**Key Features:**
- Installs build tools (gcc, cmake) for compiling llama.cpp
- Installs `llama-cpp-python[server]==0.2.90`
- CPU-only by default (OpenBLAS acceleration)
- Configurable via environment variables
- Includes curl for health checks

**Building:**
```bash
# CPU-only build
docker build -f Dockerfile.llamacpp -t kc-llm-llamacpp .

# GPU build (CUDA)
docker build -f Dockerfile.llamacpp \
  --build-arg CMAKE_ARGS="-DLLAMA_CUBLAS=ON" \
  -t kc-llm-llamacpp:cuda .
```

**Running Standalone:**
```bash
docker run -d \
  -p 8000:8000 \
  -v ./models/gguf:/models:ro \
  -e MODEL_PATH=/models/your-model.gguf \
  -e N_GPU_LAYERS=0 \
  --name llm-server \
  kc-llm-llamacpp
```

### Dockerfile.vllm

**Base Image:** `nvidia/cuda:12.1.0-cudnn8-devel-ubuntu22.04`

**Key Features:**
- CUDA 12.1 with cuDNN 8
- Python 3.11
- Installs `vllm==0.6.3`
- GPU-only (requires NVIDIA GPU)
- Configurable via environment variables
- Includes curl for health checks

**Building:**
```bash
docker build -f Dockerfile.vllm -t kc-llm-vllm .
```

**Running Standalone:**
```bash
docker run -d \
  -p 8000:8000 \
  -v ./models/hf:/models:ro \
  -e MODEL_NAME=/models/your-model \
  --gpus all \
  --shm-size 16g \
  --name llm-server \
  kc-llm-vllm
```

## Model Management

### GGUF Models (llama.cpp)

Store in `models/gguf/`:

```bash
# Download example
cd models/gguf
wget https://huggingface.co/TheBloke/Llama-2-7B-Chat-GGUF/resolve/main/llama-2-7b-chat.Q4_K_M.gguf

# Update .env
MODEL_PATH=/models/llama-2-7b-chat.Q4_K_M.gguf
```

**Recommended Quantization Levels:**
- `Q4_K_M`: Balanced (recommended for most use cases)
- `Q5_K_M`: Higher quality, larger size
- `Q8_0`: Highest quality, largest size

### HuggingFace Models (vLLM)

Store in `models/hf/`:

```bash
# Using huggingface-cli
pip install huggingface-hub

# Download example
huggingface-cli download \
  --repo-type model \
  --local-dir ./models/hf/llama-2-7b-chat \
  meta-llama/Llama-2-7b-chat-hf

# Update .env
MODEL_NAME=/models/llama-2-7b-chat
```

**Note:** vLLM requires models in SafeTensors format. Most HuggingFace models are compatible.

## Environment Configuration

Copy `.env.sample` to `.env` and configure:

```bash
cp .env.sample .env
```

**Key Variables:**

```env
# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# LLM Server
LLM_SERVER_URL=http://localhost:8000
LLM_TIMEOUT=120

# llama.cpp (when using docker-compose.llamacpp.yml)
MODEL_PATH=/models/model.gguf
N_CTX=4096
N_GPU_LAYERS=0  # 0=CPU, -1=all layers to GPU

# vLLM (when using docker-compose.vllm.yml)
MODEL_NAME=/models/model
TENSOR_PARALLEL_SIZE=1
GPU_MEMORY_UTILIZATION=0.9
MAX_MODEL_LEN=4096
```

## Health Checks

### Redis
```bash
docker-compose exec redis redis-cli ping
# Expected: PONG
```

### LLM Server (llama.cpp or vLLM)
```bash
curl http://localhost:8000/health
# Expected: {"status":"ok"} or similar

curl http://localhost:8000/v1/models
# Expected: {"data":[...]}
```

## GPU Support

### Prerequisites

**NVIDIA Docker Runtime:**
```bash
# Install nvidia-docker2
# Ubuntu/Debian
sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker

# Verify
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

### Configuration

Both `docker-compose.llamacpp.yml` and `docker-compose.vllm.yml` include GPU configuration:

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: all
          capabilities: [gpu]
```

**For llama.cpp (CPU + GPU hybrid):**
```env
N_GPU_LAYERS=-1  # Offload all layers to GPU
```

**For vLLM (GPU required):**
- Automatically uses all available GPUs
- Adjust `TENSOR_PARALLEL_SIZE` for multi-GPU setups

## Switching Between Backends

### From llama.cpp to vLLM

```bash
# Stop llama.cpp
docker-compose -f docker-compose.yml -f docker-compose.llamacpp.yml down

# Start vLLM
docker-compose -f docker-compose.yml -f docker-compose.vllm.yml up -d

# Update .env
LLM_BACKEND=vllm
MODEL_NAME=/models/your-hf-model
```

### From vLLM to llama.cpp

```bash
# Stop vLLM
docker-compose -f docker-compose.yml -f docker-compose.vllm.yml down

# Start llama.cpp
docker-compose -f docker-compose.yml -f docker-compose.llamacpp.yml up -d

# Update .env
LLM_BACKEND=llamacpp
MODEL_PATH=/models/your-model.gguf
```

## Troubleshooting

### Redis Connection Issues

```bash
# Check Redis is running
docker-compose ps redis

# Check Redis logs
docker-compose logs redis

# Test connection
docker-compose exec redis redis-cli ping
```

### LLM Server Not Starting (llama.cpp)

```bash
# Check logs
docker-compose logs llm-server

# Common issues:
# 1. Model file not found
docker-compose exec llm-server ls -lh /models/

# 2. Insufficient memory
# Reduce N_CTX or use smaller quantization

# 3. GPU layers but no GPU
# Set N_GPU_LAYERS=0 for CPU-only
```

### LLM Server Not Starting (vLLM)

```bash
# Check logs
docker-compose logs llm-server

# Common issues:
# 1. No GPU available
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi

# 2. Out of GPU memory
# Reduce GPU_MEMORY_UTILIZATION or MAX_MODEL_LEN

# 3. Model format incompatible
# Ensure model is in SafeTensors format
```

### Port Already in Use

```bash
# Find process using port 8000
# Windows
netstat -ano | findstr :8000

# Linux/Mac
lsof -i :8000

# Change port in docker-compose override file
ports:
  - "8001:8000"
```

## Production Considerations

### Security

1. **Redis Password:**
   ```yaml
   # docker-compose.yml
   redis:
     command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
   ```

2. **Network Isolation:**
   - Use internal networks for Redis
   - Expose only necessary ports
   - Consider using reverse proxy for LLM API

3. **Resource Limits:**
   ```yaml
   deploy:
     resources:
       limits:
         cpus: '4'
         memory: 8G
   ```

### Monitoring

1. **Redis Metrics:**
   ```bash
   docker-compose exec redis redis-cli INFO stats
   ```

2. **LLM Server Metrics:**
   - llama.cpp: Check logs for request timing
   - vLLM: Built-in Prometheus metrics at `/metrics`

3. **Container Health:**
   ```bash
   docker-compose ps
   docker stats
   ```

### Backup and Recovery

**Redis Data:**
```bash
# Backup
docker-compose exec redis redis-cli BGSAVE
docker cp kc-worker-redis:/data/dump.rdb ./backup/

# Restore
docker cp ./backup/dump.rdb kc-worker-redis:/data/
docker-compose restart redis
```

**Models:**
- Models are mounted read-only from host
- Back up `models/` directory regularly
- Consider using object storage (S3, MinIO) for large models

## Next Steps

1. Set up Python worker environment (see `README.md`)
2. Configure `.env` file
3. Download models to appropriate directories
4. Start infrastructure: `docker-compose -f docker-compose.yml -f docker-compose.llamacpp.yml up -d`
5. Run worker: `celery -A celery_app.celery worker --loglevel=info`
6. Test end-to-end with sample tasks

## References

- [llama-cpp-python Documentation](https://github.com/abetlen/llama-cpp-python)
- [vLLM Documentation](https://docs.vllm.ai/)
- [Redis Docker Documentation](https://hub.docker.com/_/redis)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
