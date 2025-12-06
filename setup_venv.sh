#!/bin/bash
# Setup script for Linux/macOS
# Creates a Python virtual environment and installs dependencies

set -e

echo "Creating Python virtual environment..."
python3 -m venv venv

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "Setup complete! To activate the virtual environment, run:"
echo "  source venv/bin/activate"
echo ""
echo "To start the Celery worker, run:"
echo "  celery -A celery_app.celery worker --loglevel=info"
echo ""
