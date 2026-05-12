# Developer Guide - Setup

## Purpose

This document provides comprehensive setup instructions for developers. It covers local development environment setup, Docker startup, debugging, testing, and development workflow. This documentation is essential for new developers joining the project.

---

## 1. Prerequisites

### Required Software

| Software | Version | Purpose |
|----------|---------|---------|
| Python | 3.11+ | Backend runtime |
| Node.js | 18+ | Frontend runtime |
| Docker | Latest | Container runtime |
| Docker Compose | Latest | Local orchestration |
| Git | Latest | Version control |
| Make | Latest | Build automation |

### System Requirements

- **OS**: macOS, Linux, or Windows with WSL2
- **RAM**: 16GB minimum (32GB recommended)
- **Disk**: 50GB free space
- **CPU**: 4 cores minimum

---

## 2. Repository Setup

### Clone Repository

```bash
git clone https://github.com/your-org/research-agent.git
cd research-agent
```

### Environment Variables

```bash
# Copy environment template
cp env.template .env

# Edit .env with your settings
cat .env
```

### Required Environment Variables

```bash
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/research_agent

# Redis
REDIS_URL=redis://localhost:6379/0

# Ollama
OLLAMA_BASE_URL=http://localhost:11434

# API Keys (optional for local development)
OPENAI_API_KEY=
ANTHROPIC_API_KEY=

# JWT Secret
JWT_SECRET=your-secret-key-here

# Application
DEBUG=true
LOG_LEVEL=DEBUG
```

---

## 3. Local Development Setup

### Using Docker Compose

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Manual Setup

#### Backend Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start API server
uvicorn api.main:app --reload --port 8000
```

#### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

#### Worker Setup

```bash
# Start Celery worker
celery -A workers.celery_app worker --loglevel=info --concurrency=4
```

---

## 4. Docker Services

### Service Architecture

```yaml
services:
  # API Service
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@postgres:5432/research_agent
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - postgres
      - redis

  # Frontend
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"

  # PostgreSQL
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: research_agent
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - postgres_data:/var/lib/postgresql/data

  # Redis
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

  # ChromaDB
  chromadb:
    image: chromadb/chroma:latest
    volumes:
      - chroma_data:/chroma/chroma

  # Ollama
  ollama:
    image: ollama/ollama:latest
    volumes:
      - ollama_data:/root/.ollama

  # Celery Worker
  celery-worker:
    build: .
    command: celery -A workers.celery_app worker --loglevel=info
    environment:
      - BROKER_URL=redis://redis:6379/0
      - RESULT_BACKEND=redis://redis:6379/0
    depends_on:
      - redis
```

---

## 5. Running Tests

### Unit Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_agents.py

# Run with coverage
pytest --cov=. --cov-report=html
```

### Integration Tests

```bash
# Run integration tests
pytest tests/integration/ -v

# Run with services
docker-compose up -d
pytest tests/integration/ -v
docker-compose down
```

### Frontend Tests

```bash
cd frontend

# Run unit tests
npm test

# Run e2e tests
npm run test:e2e

# Run linting
npm run lint
```

---

## 6. Development Workflow

### Code Style

```bash
# Format code
make format

# Lint code
make lint

# Type check
make typecheck
```

### Git Workflow

```bash
# Create feature branch
git checkout -b feature/my-feature

# Make changes
# ... edit code ...

# Run tests
make test

# Commit changes
git add .
git commit -m "Add my feature"

# Push to remote
git push origin feature/my-feature

# Create pull request
gh pr create
```

---

## 7. Debugging

### API Debugging

```bash
# Start with debug logging
DEBUG=true LOG_LEVEL=DEBUG uvicorn api.main:app --reload

# Use debugpy for breakpoints
python -m debugpy --listen 0.0.0.0:5678 -m uvicorn api.main:app
```

### Worker Debugging

```bash
# Start worker with verbose logging
celery -A workers.celery_app worker --loglevel=debug --concurrency=1

# Inspect tasks
celery -A workers.celery_app inspect active
celery -A workers.celery_app inspect scheduled
```

### Database Debugging

```bash
# Connect to PostgreSQL
psql postgresql://postgres:postgres@localhost:5432/research_agent

# View tables
\dt

# Query data
SELECT * FROM sessions LIMIT 10;
```

---

## 8. Common Issues

### Port Already in Use

```bash
# Find process using port
lsof -i :8000

# Kill process
kill -9 <PID>
```

### Database Connection Issues

```bash
# Check PostgreSQL is running
docker-compose ps

# Check connection
docker-compose exec postgres pg_isready

# Reset database
docker-compose down -v
docker-compose up -d
```

### Ollama Not Available

```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Pull required models
ollama pull qwen3
ollama pull llama3
ollama pull mistral
```

---

## Related Documentation

- [Local Development](local-development.md)
- [Contributing](contributing.md)
- [Troubleshooting](../troubleshooting/common-issues.md)