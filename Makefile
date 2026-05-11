# Research OS - Development Makefile
# Provides developer-friendly commands for common tasks

.PHONY: help install test lint format typecheck clean pre-commit ci \
	docker-build docker-up docker-down docker-logs \
	run-api run-worker run-dev

# Default target
help:
	@echo "Research OS - Development Commands"
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@echo "Setup:"
	@echo "  install        Install all dependencies (includes dev dependencies)"
	@echo "  clean          Remove caches, build artifacts, and generated files"
	@echo ""
	@echo "Code Quality:"
	@echo "  lint           Run ruff linter (ruff check)"
	@echo "  format         Format code with black and fix linting issues"
	@echo "  typecheck      Run mypy type checker"
	@echo "  pre-commit     Run all pre-commit hooks"
	@echo "  ci             Simulate CI locally (lint + typecheck + test)"
	@echo ""
	@echo "Testing:"
	@echo "  test           Run all tests with pytest"
	@echo ""
	@echo "Docker:"
	@echo "  docker-build   Build all Docker images"
	@echo "  docker-up      Start all Docker services"
	@echo "  docker-down    Stop all Docker services"
	@echo "  docker-logs    Follow Docker logs"
	@echo ""
	@echo "Development:"
	@echo "  run-api        Start FastAPI server with hot reload"
	@echo "  run-worker      Start Celery worker"
	@echo "  run-dev        Start API and worker together"
	@echo ""

# ============================================================================
# Setup
# ============================================================================

install:
	@echo "==> Installing dependencies..."
	@pip install -r requirements.txt
	@pip install -e ".[dev]" 2>/dev/null || pip install -e .
	@echo "==> Dependencies installed successfully"

clean:
	@echo "==> Cleaning up..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "dist" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "build" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@find . -type f -name ".coverage" -delete 2>/dev/null || true
	@find . -type f -name ".coverage.*" -delete 2>/dev/null || true
	@rm -rf .hypothesis/ 2>/dev/null || true
	@echo "==> Cleanup complete"

# ============================================================================
# Code Quality
# ============================================================================

lint:
	@echo "==> Running ruff linter..."
	@ruff check .
	@echo "==> Linting passed"

format:
	@echo "==> Formatting code with ruff..."
	@ruff format .
	@echo "==> Running ruff --fix..."
	@ruff check --fix .

typecheck:
	@echo "==> Running mypy type checker..."
	@mypy .
	@echo "==> Type checking passed"

pre-commit:
	@echo "==> Running pre-commit hooks..."
	@pre-commit run --all-files
	@echo "==> Pre-commit checks passed"

ci: lint typecheck test
	@echo ""
	@echo "==> CI simulation complete - all checks passed!"

# ============================================================================
# Testing
# ============================================================================

test:
	@echo "==> Running tests..."
	@python -m pytest -v --tb=short
	@echo "==> Tests complete"

test-cov:
	@echo "==> Running tests with coverage..."
	@python -m pytest -v --cov=. --cov-report=term-missing --cov-report=html
	@echo "==> Coverage report generated in htmlcov/index.html"

# ============================================================================
# Docker
# ============================================================================

docker-build:
	@echo "==> Building Docker images..."
	@docker compose -f deployment/docker-compose.yml build
	@echo "==> Docker images built successfully"

docker-up:
	@echo "==> Starting Docker services..."
	@docker compose -f deployment/docker-compose.yml up -d
	@echo "==> Docker services started"
	@echo "   - API:          http://localhost:8000"
	@echo "   - PostgreSQL:  localhost:5432"
	@echo "   - Redis:       localhost:6379"
	@echo "   - Ollama:      http://localhost:11434"
	@echo "   - ChromaDB:    localhost:8000"

docker-down:
	@echo "==> Stopping Docker services..."
	@docker compose -f deployment/docker-compose.yml down
	@echo "==> Docker services stopped"

docker-logs:
	@echo "==> Following Docker logs (Ctrl+C to exit)..."
	@docker compose -f deployment/docker-compose.yml logs -f

docker-restart: docker-down docker-up
	@echo "==> Docker services restarted"

# ============================================================================
# Development Servers
# ============================================================================

run-api:
	@echo "==> Starting FastAPI server..."
	@echo "   API will be available at http://localhost:8000"
	@echo "   Docs at http://localhost:8000/docs"
	@uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

run-worker:
	@echo "==> Starting Celery worker..."
	@celery -A workers.celery_app worker -Q research,browser -l info --concurrency=2

run-beat:
	@echo "==> Starting Celery beat scheduler..."
	@celery -A workers.celery_app beat -l info

run-dev:
	@echo "==> Starting development environment..."
	@echo "   Starting API server..."
	@uvicorn api.main:app --reload --host 0.0.0.0 --port 8000 &
	@API_PID=$$!
	@echo "   Starting Celery worker..."
	@celery -A workers.celery_app worker -Q research,browser -l info &
	@WORKER_PID=$$!
	@echo ""
	@echo "==> Development servers started"
	@echo "   - API: http://localhost:8000 (PID: $$API_PID)"
	@echo "   - Worker PID: $$WORKER_PID"
	@echo ""
	@echo "Press Ctrl+C to stop all servers"
	@wait