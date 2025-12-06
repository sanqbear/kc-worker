@echo off
REM Start Celery worker on Windows
REM Usage: start_worker.bat

echo Starting Celery Worker...
echo.

REM Check if virtual environment is activated
if not defined VIRTUAL_ENV (
    echo ERROR: Virtual environment not activated!
    echo Please run: venv\Scripts\activate.bat
    exit /b 1
)

REM Check if .env file exists
if not exist .env (
    echo WARNING: .env file not found!
    echo Creating .env from .env.sample...
    copy .env.sample .env
    echo Please edit .env with your configuration and run again.
    exit /b 1
)

REM Start Celery worker
echo Starting Celery worker with settings:
echo - Log level: INFO
echo - Concurrency: 4
echo - Prefetch multiplier: 1
echo.

celery -A celery_app.celery worker ^
    --loglevel=info ^
    --concurrency=4 ^
    --prefetch-multiplier=1 ^
    --max-tasks-per-child=1000 ^
    --task-events ^
    --without-gossip ^
    --without-mingle

echo.
echo Celery worker stopped.
