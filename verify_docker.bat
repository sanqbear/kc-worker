@echo off
REM Docker Infrastructure Verification Script (Windows)
REM Tests all Docker components for the Knowledge Center AI Worker

setlocal enabledelayedexpansion

echo ======================================
echo Knowledge Center Worker - Docker Verification
echo ======================================
echo.

REM Check if Docker is installed
echo Checking prerequisites...
docker --version >nul 2>&1
if !errorlevel! neq 0 (
    echo [ERROR] Docker is not installed
    exit /b 1
)
echo [OK] Docker is installed
docker --version

docker-compose --version >nul 2>&1
if !errorlevel! neq 0 (
    echo [ERROR] Docker Compose is not installed
    exit /b 1
)
echo [OK] Docker Compose is installed
docker-compose --version

echo.

REM Check if .env file exists
echo Checking configuration...
if not exist .env (
    echo [WARNING] .env file not found, using .env.sample defaults
    if exist .env.sample (
        echo   You can create .env by running: copy .env.sample .env
    )
) else (
    echo [OK] .env file exists
)

echo.

REM Test Redis service
echo Testing Redis service...
docker-compose up -d redis
timeout /t 5 /nobreak >nul

docker-compose ps redis | findstr /C:"Up" >nul
if !errorlevel! equ 0 (
    echo [OK] Redis container is running

    REM Test Redis connection
    docker-compose exec -T redis redis-cli ping | findstr /C:"PONG" >nul
    if !errorlevel! equ 0 (
        echo [OK] Redis is responding to ping
    ) else (
        echo [ERROR] Redis is not responding
    )
) else (
    echo [ERROR] Redis container failed to start
)

echo.

REM Check model directories
echo Checking model directories...
if exist models\gguf (
    echo [OK] models\gguf directory exists
    dir /b models\gguf\*.gguf >nul 2>&1
    if !errorlevel! equ 0 (
        echo   Found GGUF model(s)
    ) else (
        echo [WARNING] No GGUF models found in models\gguf\
        echo   Download models before starting llama.cpp server
    )
) else (
    echo [ERROR] models\gguf directory not found
)

if exist models\hf (
    echo [OK] models\hf directory exists
    dir /b models\hf\ >nul 2>&1
    if !errorlevel! equ 0 (
        echo   Found HuggingFace model(s)
    ) else (
        echo [WARNING] No HuggingFace models found in models\hf\
        echo   Download models before starting vLLM server
    )
) else (
    echo [ERROR] models\hf directory not found
)

echo.

REM Check Docker images
echo Checking Docker images...
docker images | findstr /C:"redis" >nul
if !errorlevel! equ 0 (
    echo [OK] Redis image exists
) else (
    echo [WARNING] Redis image not found locally (will be pulled on first run)
)

echo.

REM Test Dockerfiles
echo Testing llama.cpp Dockerfile...
if exist Dockerfile.llamacpp (
    echo [OK] Dockerfile.llamacpp exists
    echo   To build: docker build -f Dockerfile.llamacpp -t kc-llm-llamacpp .
) else (
    echo [ERROR] Dockerfile.llamacpp not found
)

echo Testing vLLM Dockerfile...
if exist Dockerfile.vllm (
    echo [OK] Dockerfile.vllm exists
    echo   To build: docker build -f Dockerfile.vllm -t kc-llm-vllm .
) else (
    echo [ERROR] Dockerfile.vllm not found
)

echo.

REM Check Docker Compose files
echo Checking Docker Compose configurations...
for %%f in (docker-compose.yml docker-compose.llamacpp.yml docker-compose.vllm.yml) do (
    if exist %%f (
        echo [OK] %%f exists
        docker-compose -f %%f config >nul 2>&1
        if !errorlevel! equ 0 (
            echo   YAML syntax is valid
        ) else (
            echo [ERROR] %%f has invalid YAML syntax
        )
    ) else (
        echo [ERROR] %%f not found
    )
)

echo.

REM Network check
echo Checking Docker networks...
docker network ls | findstr /C:"worker-network" >nul
if !errorlevel! equ 0 (
    echo [OK] worker-network exists
) else (
    echo   worker-network will be created when services start
)

echo.

REM Volume check
echo Checking Docker volumes...
docker volume ls | findstr /C:"worker_redis-data" >nul
if !errorlevel! equ 0 (
    echo [OK] redis-data volume exists
) else (
    echo   redis-data volume will be created when Redis starts
)

echo.

REM GPU check (optional)
echo Checking GPU support (optional)...
nvidia-smi >nul 2>&1
if !errorlevel! equ 0 (
    echo [OK] nvidia-smi is available
    docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi >nul 2>&1
    if !errorlevel! equ 0 (
        echo [OK] Docker can access NVIDIA GPUs
    ) else (
        echo [WARNING] Docker cannot access GPUs (nvidia-docker2 may not be installed)
        echo   GPU support is optional for llama.cpp, required for vLLM
    )
) else (
    echo [WARNING] nvidia-smi not found (GPU support disabled)
    echo   llama.cpp can run on CPU, but vLLM requires GPU
)

echo.
echo ======================================
echo Verification Summary
echo ======================================
echo.

REM Cleanup
echo Cleaning up test containers...
docker-compose down >nul 2>&1
echo [OK] Cleanup complete

echo.
echo Next Steps:
echo 1. Create .env file: copy .env.sample .env
echo 2. Download models to models\gguf\ or models\hf\
echo 3. Start Redis: docker-compose up -d
echo 4. Start LLM server (choose one):
echo    - llama.cpp: docker-compose -f docker-compose.yml -f docker-compose.llamacpp.yml up -d
echo    - vLLM: docker-compose -f docker-compose.yml -f docker-compose.vllm.yml up -d
echo 5. Set up Python environment: setup_venv.bat
echo 6. Run worker: celery -A celery_app.celery worker --loglevel=info
echo.
echo For detailed documentation, see DOCKER.md
echo.

endlocal
