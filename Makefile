.PHONY: help install dev test lint format docker-up docker-down clean

help:
	@echo "Research OS - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  install      Install dependencies"
	@echo "  dev          Run development server"
	@echo ""
	@echo "Testing:"
	@echo "  test         Run tests"
	@echo "  lint         Run linters"
	@echo "  format       Format code"
	@echo ""
	@echo "Docker:"
	@echo "  docker-up    Start all services"
	@echo "  docker-down  Stop all services"
	@echo ""
	@echo "Utilities:"
	@echo "  clean        Clean up generated files"

install:
	@echo "Installing dependencies..."
	pip install -r requirements.txt

dev:
	@echo "Starting development server..."
	uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

test:
	@echo "Running tests..."
	pytest -v --cov=. --cov-report=html

lint:
	@echo "Running linters..."
	ruff check .
	mypy .

format:
	@echo "Formatting code..."
	ruff format .
	ruff check --fix .

docker-up:
	@echo "Starting Docker services..."
	cd deployment && docker-compose up -d

docker-down:
	@echo "Stopping Docker services..."
	cd deployment && docker-compose down

docker-logs:
	@echo "Showing Docker logs..."
	cd deployment && docker-compose logs -f

clean:
	@echo "Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage 2>/dev/null || true