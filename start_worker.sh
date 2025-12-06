#!/bin/bash
# Start Celery worker on Linux/macOS
# Usage: ./start_worker.sh

set -e

echo "Starting Celery Worker..."
echo ""

# Check if virtual environment is activated
if [[ -z "${VIRTUAL_ENV}" ]]; then
    echo "ERROR: Virtual environment not activated!"
    echo "Please run: source venv/bin/activate"
    exit 1
fi

# Check if .env file exists
if [[ ! -f .env ]]; then
    echo "WARNING: .env file not found!"
    echo "Creating .env from .env.sample..."
    cp .env.sample .env
    echo "Please edit .env with your configuration and run again."
    exit 1
fi

# Start Celery worker
echo "Starting Celery worker with settings:"
echo "- Log level: INFO"
echo "- Concurrency: 4"
echo "- Prefetch multiplier: 1"
echo ""

celery -A celery_app.celery worker \
    --loglevel=info \
    --concurrency=4 \
    --prefetch-multiplier=1 \
    --max-tasks-per-child=1000 \
    --task-events \
    --without-gossip \
    --without-mingle

echo ""
echo "Celery worker stopped."
