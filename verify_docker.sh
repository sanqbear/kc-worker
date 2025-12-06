#!/bin/bash
# Docker Infrastructure Verification Script
# Tests all Docker components for the Knowledge Center AI Worker

set -e

echo "======================================"
echo "Knowledge Center Worker - Docker Verification"
echo "======================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "  $1"
}

# Check if Docker is installed
echo "Checking prerequisites..."
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed"
    exit 1
fi
print_success "Docker is installed: $(docker --version)"

if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose is not installed"
    exit 1
fi
print_success "Docker Compose is installed: $(docker-compose --version)"

echo ""

# Check if .env file exists
echo "Checking configuration..."
if [ ! -f .env ]; then
    print_warning ".env file not found, using .env.sample defaults"
    if [ -f .env.sample ]; then
        print_info "You can create .env by running: cp .env.sample .env"
    fi
else
    print_success ".env file exists"
fi

echo ""

# Test Redis service
echo "Testing Redis service..."
docker-compose up -d redis
sleep 5

if docker-compose ps redis | grep -q "Up"; then
    print_success "Redis container is running"

    # Test Redis connection
    if docker-compose exec -T redis redis-cli ping | grep -q "PONG"; then
        print_success "Redis is responding to ping"
    else
        print_error "Redis is not responding"
    fi
else
    print_error "Redis container failed to start"
fi

echo ""

# Check model directories
echo "Checking model directories..."
if [ -d "models/gguf" ]; then
    print_success "models/gguf directory exists"
    GGUF_COUNT=$(find models/gguf -name "*.gguf" 2>/dev/null | wc -l)
    if [ "$GGUF_COUNT" -gt 0 ]; then
        print_info "Found $GGUF_COUNT GGUF model(s)"
    else
        print_warning "No GGUF models found in models/gguf/"
        print_info "Download models before starting llama.cpp server"
    fi
else
    print_error "models/gguf directory not found"
fi

if [ -d "models/hf" ]; then
    print_success "models/hf directory exists"
    HF_COUNT=$(find models/hf -maxdepth 1 -type d 2>/dev/null | wc -l)
    if [ "$HF_COUNT" -gt 1 ]; then
        print_info "Found $((HF_COUNT-1)) HuggingFace model(s)"
    else
        print_warning "No HuggingFace models found in models/hf/"
        print_info "Download models before starting vLLM server"
    fi
else
    print_error "models/hf directory not found"
fi

echo ""

# Check Docker images
echo "Checking Docker images..."
if docker images | grep -q "redis"; then
    print_success "Redis image exists"
else
    print_warning "Redis image not found locally (will be pulled on first run)"
fi

echo ""

# Test llama.cpp Dockerfile (build only, don't start)
echo "Testing llama.cpp Dockerfile..."
if [ -f "Dockerfile.llamacpp" ]; then
    print_success "Dockerfile.llamacpp exists"
    print_info "To build: docker build -f Dockerfile.llamacpp -t kc-llm-llamacpp ."
else
    print_error "Dockerfile.llamacpp not found"
fi

# Test vLLM Dockerfile (build only, don't start)
echo "Testing vLLM Dockerfile..."
if [ -f "Dockerfile.vllm" ]; then
    print_success "Dockerfile.vllm exists"
    print_info "To build: docker build -f Dockerfile.vllm -t kc-llm-vllm ."
else
    print_error "Dockerfile.vllm not found"
fi

echo ""

# Check Docker Compose files
echo "Checking Docker Compose configurations..."
FILES=("docker-compose.yml" "docker-compose.llamacpp.yml" "docker-compose.vllm.yml")
for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        print_success "$file exists"
        # Validate YAML syntax
        if docker-compose -f "$file" config > /dev/null 2>&1; then
            print_info "YAML syntax is valid"
        else
            print_error "$file has invalid YAML syntax"
        fi
    else
        print_error "$file not found"
    fi
done

echo ""

# Network check
echo "Checking Docker networks..."
if docker network ls | grep -q "worker-network"; then
    print_success "worker-network exists"
else
    print_info "worker-network will be created when services start"
fi

echo ""

# Volume check
echo "Checking Docker volumes..."
if docker volume ls | grep -q "worker_redis-data"; then
    print_success "redis-data volume exists"
    VOLUME_SIZE=$(docker volume inspect worker_redis-data --format '{{ .Mountpoint }}' | xargs du -sh 2>/dev/null | cut -f1)
    print_info "Volume size: ${VOLUME_SIZE:-unknown}"
else
    print_info "redis-data volume will be created when Redis starts"
fi

echo ""

# GPU check (optional)
echo "Checking GPU support (optional)..."
if command -v nvidia-smi &> /dev/null; then
    print_success "nvidia-smi is available"
    if docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi &> /dev/null; then
        print_success "Docker can access NVIDIA GPUs"
        GPU_COUNT=$(nvidia-smi --query-gpu=name --format=csv,noheader | wc -l)
        print_info "Available GPUs: $GPU_COUNT"
    else
        print_warning "Docker cannot access GPUs (nvidia-docker2 may not be installed)"
        print_info "GPU support is optional for llama.cpp, required for vLLM"
    fi
else
    print_warning "nvidia-smi not found (GPU support disabled)"
    print_info "llama.cpp can run on CPU, but vLLM requires GPU"
fi

echo ""
echo "======================================"
echo "Verification Summary"
echo "======================================"
echo ""

# Cleanup
echo "Cleaning up test containers..."
docker-compose down > /dev/null 2>&1
print_success "Cleanup complete"

echo ""
echo "Next Steps:"
echo "1. Create .env file: cp .env.sample .env"
echo "2. Download models to models/gguf/ or models/hf/"
echo "3. Start Redis: docker-compose up -d"
echo "4. Start LLM server (choose one):"
echo "   - llama.cpp: docker-compose -f docker-compose.yml -f docker-compose.llamacpp.yml up -d"
echo "   - vLLM: docker-compose -f docker-compose.yml -f docker-compose.vllm.yml up -d"
echo "5. Set up Python environment: ./setup_venv.sh (or setup_venv.bat on Windows)"
echo "6. Run worker: celery -A celery_app.celery worker --loglevel=info"
echo ""
echo "For detailed documentation, see DOCKER.md"
echo ""
