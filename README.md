# AI Research Agent - Autonomous AI Research Agent

A production-grade autonomous AI Research Agent built with LangGraph, FastAPI, Celery, and Ollama.

## Features

- **Multi-Agent Orchestration**: LangGraph-based workflow with Planner, Router, Reflection, and Writer agents
- **Distributed Execution**: Celery workers with Redis broker for scalable task processing
- **Local AI Execution**: Ollama integration for privacy-first LLM inference
- **Browser Automation**: Playwright-based isolated browser containers
- **Memory Systems**: PostgreSQL, Redis, and ChromaDB for persistent storage
- **Observability**: Structured logging, metrics, and tracing support

## Architecture

```
┌────────────────────┐
│     Frontend UI    │
└─────────┬──────────┘
          │
          ▼
┌────────────────────────┐
│     FastAPI Gateway    │
└─────────┬──────────────┘
          │
          ▼
┌────────────────────────────────┐
│    LangGraph Orchestrator      │
└────────────┬───────────────────┘
             │
             ▼
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
│            Redis Broker             │
┃                                      ┃
┃  ┌────────────────┐   ┌────────────────┐
┃  │ Celery Worker  │   │ Celery Worker  │
┃  │ Research Pool  │   │ Browser Pool   │
┃  └────────────────┘   └────────────────┘
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Redis (optional, included in Docker)
- PostgreSQL (optional, included in Docker)
- Ollama (optional, included in Docker)

### Installation

1. Clone the repository
2. Copy `.env.example` to `.env` and configure
3. Run `make install` or `pip install -r requirements.txt`

### Running with Docker

```bash
cd deployment
docker-compose up -d
```

### Running Locally

```bash
# Start the API server
make dev

# In another terminal, start Celery worker
celery -A workers.celery_app worker -l info
```

## API Endpoints

- `GET /health` - Health check
- `GET /health/live` - Liveness probe
- `GET /health/ready` - Readiness probe
- `POST /api/v1/research` - Create research task
- `GET /api/v1/research/{session_id}/status` - Get task status
- `WebSocket /ws/{session_id}` - Real-time updates

## Development

```bash
# Run tests
make test

# Run linters
make lint

# Format code
make format
```

## Project Structure

```
research-agent/
├── agents/          # Agent implementations
├── api/             # FastAPI application
├── graphs/          # LangGraph definitions
├── models/          # LLM clients
├── workers/         # Celery tasks
├── observability/   # Logging and metrics
├── deployment/      # Docker configuration
└── tests/           # Test suite
```

## License

MIT