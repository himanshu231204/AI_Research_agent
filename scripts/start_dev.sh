#!/bin/bash

# Research OS - Development Startup Script

set -e

echo "=========================================="
echo "Research OS - Development Environment"
echo "=========================================="

# Check for .env file
if [ ! -f .env ]; then
    echo "Creating .env from template..."
    cp .env.example .env
    echo "Please edit .env with your settings"
fi

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $PYTHON_VERSION"

# Install dependencies if needed
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing dependencies..."
pip install -r requirements.txt

# Check Docker
if command -v docker &> /dev/null; then
    echo "Docker found"
    docker --version
else
    echo "Warning: Docker not found"
fi

# Check Docker Compose
if command -v docker-compose &> /dev/null; then
    echo "Docker Compose found"
    docker-compose --version
elif command -v docker &> /dev/null && docker compose version &> /dev/null; then
    echo "Docker Compose (plugin) found"
else
    echo "Warning: Docker Compose not found"
fi

echo ""
echo "=========================================="
echo "Setup complete!"
echo ""
echo "To start the API server:"
echo "  uvicorn api.main:app --reload"
echo ""
echo "To start Celery worker:"
echo "  celery -A workers.celery_app worker -l info"
echo ""
echo "To start all services with Docker:"
echo "  cd deployment && docker-compose up"
echo "=========================================="