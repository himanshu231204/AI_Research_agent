# AGENT.md

# Autonomous AI Research Operating System

## Production-Grade Multi-Agent Architecture (FINAL VERSION)

---

# 1. Vision

Build a production-grade autonomous AI Research Operating System capable of:

* Autonomous planning
* Multi-source research
* GitHub repository analysis
* PDF/document analysis
* Browser automation
* Long-term memory
* Reflection and self-correction
* Report generation
* Human-in-the-loop workflows
* Multi-model orchestration
* Local AI execution using Ollama
* Cloud fallback inference
* MCP-based tool ecosystem
* Distributed execution
* Fault-tolerant orchestration

---

# 2. Core Objectives

The system should:

1. Accept complex research tasks
2. Decompose tasks autonomously
3. Execute parallel research workflows
4. Validate findings
5. Reflect and improve responses
6. Persist memory across sessions
7. Generate production-quality reports
8. Support local and cloud LLMs
9. Provide observability and tracing
10. Support scalable deployment
11. Survive worker crashes
12. Prevent infinite loops
13. Track cost and token usage

---

# 3. High-Level Architecture

```text
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
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
│                Distributed Queue Layer                     │
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
│                                                            │
│  Redis Broker                                              │
│  Celery Workers                                            │
│  Dead Letter Queue                                         │
│  Retry Queues                                              │
│                                                            │
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                              │
                              ▼
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
│                    Multi-Agent Layer                       │
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
│                                                            │
│  Planner Agent                                             │
│  Task Router Agent                                         │
│  Web Research Agent                                        │
│  GitHub Analysis Agent                                     │
│  PDF/RAG Agent                                             │
│  Browser Automation Agent                                  │
│  Memory Agent                                              │
│  Reflection/Critic Agent                                   │
│  Writer Agent                                              │
│  Citation Agent                                            │
│                                                            │
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                              │
                              ▼
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
│                    Tool + MCP Layer                        │
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
│                                                            │
│  Tavily Search                                             │
│  Brave Search                                              │
│  Playwright                                                │
│  GitHub MCP Server                                         │
│  Filesystem MCP Server                                     │
│  Browser MCP Server                                        │
│  Terminal MCP Server                                       │
│                                                            │
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                              │
                              ▼
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
│                     LLM Routing Layer                      │
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
│                                                            │
│  Local Models (Ollama)                                     │
│   ├── qwen3                                                │
│   ├── llama3                                               │
│   ├── mistral                                              │
│   └── deepseek-coder                                       │
│                                                            │
│  Cloud Fallback Models                                     │
│   ├── GPT-5 or grok                                               │
│   ├── Claude or openrouter                                            │
│   └── Gemini  
                                             │
│                                                            │
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                              │
                              ▼
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
│                   Persistence Layer                        │
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
│                                                            │
│  PostgreSQL                                                │
│  Redis                                                     │
│  ChromaDB / Qdrant                                         │
│                                                            │
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

# 4. Frontend Layer

## Responsibilities

* Streaming chat UI
* Workflow visualization
* Agent activity panel
* Research timeline
* Source citations
* Human approvals
* Memory inspection

## Recommended Stack

* Next.js
* React
* TailwindCSS
* ShadCN
* WebSockets

---

# 5. API Gateway

## Responsibilities

* Authentication
* Session management
* Rate limiting
* WebSocket handling
* Request validation
* Streaming APIs

## Recommended Stack

* FastAPI
* Uvicorn
* Pydantic

---

# 6. LangGraph Orchestrator

## Responsibilities

* Stateful orchestration
* Node routing
* Reflection cycles
* Interrupt handling
* Retry coordination
* Streaming state updates

## Why LangGraph

LangGraph provides:

* Stateful execution
* Multi-agent orchestration
* Cyclic workflows
* Durable execution
* Streaming
* Human-in-the-loop support

---

# 7. Distributed Queue Architecture (CRITICAL)

The system MUST NOT rely solely on asyncio.

Use:

* Celery
* Redis Broker
* Redis Result Backend

---

## Queue Architecture

```text
                ┌────────────────────┐
                │  FastAPI Gateway   │
                └─────────┬──────────┘
                          │
                          ▼
                ┌────────────────────┐
                │   LangGraph Core   │
                └─────────┬──────────┘
                          │
                          ▼
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
│            Redis Broker             │
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
          │            │
          ▼            ▼

 ┌────────────────┐   ┌────────────────┐
 │ Celery Worker  │   │ Celery Worker  │
 │ Research Pool  │   │ Browser Pool   │
 └────────────────┘   └────────────────┘
```

---

## Queue Types

### High Priority Queue

Used for:

* orchestration
* user actions
* retries

### Research Queue

Used for:

* web research
* PDF parsing
* GitHub analysis

### Browser Queue

Used for:

* Playwright tasks
* autonomous browsing

### Dead Letter Queue

Used for:

* failed tasks
* timeout recovery
* debugging

---

## Celery Configuration

```python
task_acks_late = True
worker_prefetch_multiplier = 1
task_track_started = True
task_serializer = "json"
result_serializer = "json"
broker_connection_retry_on_startup = True
```

---

# 8. AsyncIO vs Celery Responsibilities

## AsyncIO Responsibilities

Use asyncio for:

* concurrent HTTP calls
* embedding generation
* retrieval operations
* lightweight concurrency

## Celery Responsibilities

Use Celery for:

* long-running workflows
* browser automation
* report generation
* background orchestration
* autonomous agents

---

# 9. Agent Architecture

---

## 9.1 Planner Agent

### Responsibilities

* Query decomposition
* Planning
* Prioritization
* Strategy generation

### Model

* qwen3

---

## 9.2 Task Router Agent

### Responsibilities

* Determine required tools
* Route tasks to specialized agents

---

## 9.3 Web Research Agent

### Responsibilities

* Search the internet
* Summarize findings
* Rank sources

### Tools

* Tavily
* Brave Search

---

## 9.4 GitHub Research Agent

### Responsibilities

* Analyze repositories
* Parse README files
* Extract architecture

### MCP Tools

* GitHub MCP
* Filesystem MCP

---

## 9.5 PDF/RAG Agent

### Responsibilities

* Chunk documents
* Generate embeddings
* Retrieve context
* Summarize findings

### Stack

* ChromaDB
* RecursiveTextSplitter
* nomic-embed-text

---

## 9.6 Browser Automation Agent

### Responsibilities

* Navigate websites
* Extract dynamic content
* Interact with forms

### Stack

* Playwright
* Browser MCP

---

## 9.7 Memory Agent

### Responsibilities

* Store memory
* Compress context
* Retrieve semantic history

### Storage

* Redis
* PostgreSQL
* ChromaDB

---

## 9.8 Reflection/Critic Agent

### Responsibilities

* Detect hallucinations
* Validate outputs
* Improve reports
* Trigger additional research

---

## 9.9 Writer Agent

### Responsibilities

* Aggregate findings
* Write reports
* Improve readability

---

## 9.10 Citation Agent

### Responsibilities

* Track sources
* Generate references
* Validate citations

---

# 10. Updated LangGraph Workflow

```text
START
   ↓
Planner Agent
   ↓
Task Router
   ↓
Dispatch Tasks to Celery Queue
   ↓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
↓              ↓                ↓
Web Worker   PDF Worker    GitHub Worker
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ↓
Aggregator Node
   ↓
Reflection Agent
   ↓
reflection_count >= max?
   ↓ YES
Writer Agent
   ↓ NO
Research Loop
   ↓
Citation Agent
   ↓
END
```

---

# 11. Parallel Execution Strategy

## Goal

Maximize concurrency and throughput.

### Parallel Tasks

* Web searches
* GitHub analysis
* PDF retrieval
* Embedding generation

### Execution Model

* asyncio
* Celery workers
* async LangGraph nodes

---

# 12. Updated State Schema

```python
from typing import TypedDict, List, Dict, Optional


class ResearchState(TypedDict):
    session_id: str

    query: str

    tasks: List[dict]
    active_tasks: List[str]
    completed_tasks: List[str]
    failed_tasks: List[dict]

    findings: List[dict]
    sources: List[str]

    memory_context: Dict

    reflections: List[str]
    reflection_count: int
    max_reflections: int

    draft_report: str
    final_report: str

    current_agent: str
    next_action: str

    error_state: Optional[dict]

    requires_human_input: bool

    token_usage: Dict[str, int]

    metadata: Dict
```

---

# 13. Reflection Safety Guardrails

Autonomous reflection loops can become infinite.

The orchestrator MUST enforce hard reflection limits.

## Required Logic

```python
def should_continue_reflection(state):

    if state["reflection_count"] >= state["max_reflections"]:
        return "writer"

    return "research"
```

## Recommended Defaults

```python
reflection_count = 0
max_reflections = 3
```

---

# 14. Memory Architecture

---

## 14.1 Short-Term Memory

Stored in graph state.

Purpose:

* temporary reasoning
* active workflow context

---

## 14.2 Long-Term Memory

### PostgreSQL

Store:

* sessions
* reports
* tasks
* user history

### Redis

Store:

* cache
* queues
* active sessions

### ChromaDB

Store:

* embeddings
* semantic memory

---

# 15. Vector Database Strategy

## Development Phase

Use:

* ChromaDB

## Production Scale Phase

Migrate to:

* Qdrant

## Migration Strategy

Abstract vector operations behind:

```python
class VectorStoreProvider:
    ...
```

---

# 16. Multi-Model Routing

| Task          | Primary Model  | Fallback |
| ------------- | -------------- | -------- |
| Planning      | qwen3          | GPT-5    |
| Coding        | deepseek-coder | Claude   |
| Reflection    | mistral        | Gemini   |
| Summarization | llama3         | Claude   |

---

# 17. Hybrid LLM Routing Strategy

The system MUST support automatic cloud fallback when:

* Ollama fails
* GPU memory is exhausted
* local inference times out
* queue latency is high

---

## Routing Flow

```text
Primary Local Model
        ↓ FAIL
Cloud Fallback Model
```

---

# 18. MCP Integration

## MCP Servers

### Filesystem MCP

* local file operations

### GitHub MCP

* repository analysis

### Browser MCP

* browser automation

### Terminal MCP

* shell execution

---

# 19. Tool Architecture

## Research Tools

* Tavily
* Brave Search
* Scrapers

## Analysis Tools

* PDF parsers
* GitHub analyzers

## Automation Tools

* Browser automation
* Terminal execution

---

# 20. RAG Pipeline

```text
Document Upload
      ↓
Chunking
      ↓
Embedding Generation
      ↓
Vector Storage
      ↓
Retriever
      ↓
Context Injection
```

---

# 21. Human-in-the-Loop

## Approval Checkpoints

* Approve execution plans
* Approve browser actions
* Approve exports

---

# 22. Streaming Architecture

## Streaming Types

### Token Streaming

LLM token generation

### Workflow Streaming

Agent state updates

### Event Streaming

Tool execution events

---

# 23. Observability

## Metrics

* latency
* token usage
* retries
* failures
* execution paths

## Stack

* LangSmith
* OpenTelemetry
* Grafana
* Prometheus

---

# 24. Database Schema

## PostgreSQL Tables

* users
* sessions
* reports
* tasks
* citations
* memories
* execution_logs

---

# 25. Deployment Architecture

```text
Frontend (Vercel)
        ↓
API Gateway
        ↓
Dockerized Services
        ↓
Kubernetes Cluster
```

---

# 26. Docker Services

```yaml
services:
  frontend:
  api:
  postgres:
  redis:
  celery-worker:
  celery-beat:
  chromadb:
  ollama:
  browser-sandbox:
  monitoring:
```

---

# 27. Browser Sandbox Isolation (CRITICAL)

The Browser Agent MUST run in an isolated container.

Never run Playwright inside the API container.

---

## Security Rules

* isolated Docker network
* egress-only internet access
* ephemeral browser sessions
* no shared volumes
* restricted filesystem access

---

# 28. Security

## Required

* JWT authentication
* encrypted secrets
* browser isolation
* rate limiting
* sandboxed execution
* audit logging

---

# 29. Scalability

## Scaling Strategies

### Horizontal Workers

Scale agents independently.

### Queue-Based Execution

Use Celery.

### Model Routing

Use lightweight models for small tasks.

### Distributed Vector Search

Use Qdrant clustering.

---

# 30. Failure Handling

## Retry Strategy

* exponential backoff
* dead-letter queues
* fallback models
* fallback tools

---

# 31. Recommended Folder Structure

```text
research-os/
│
├── agents/
├── graphs/
├── tools/
├── memory/
├── models/
├── api/
├── frontend/
├── workers/
├── prompts/
├── database/
├── observability/
├── deployment/
├── tests/
└── docs/
```

---

# 32. Development Phases

## Phase 1

Core LangGraph orchestration

## Phase 2

Distributed execution with Celery

## Phase 3

Reflection safety + retries

## Phase 4

MCP integration

## Phase 5

Hybrid local/cloud routing

## Phase 6

Advanced memory + vector scaling

## Phase 7

Production Kubernetes deployment

## Phase 8

Multi-tenant architecture

---

# 33. Future Enhancements

* autonomous browsing
* AI-generated PPTs
* multi-user collaboration
* voice interface
* workflow templates
* autonomous coding agents
* agent marketplace

---

# 34. Final Goal

The final system should behave like:

* Perplexity
* Manus
* OpenDevin
* Claude Code

but with:

* modular LangGraph orchestration
* local-first AI execution
* cloud fallback resilience
* production observability
* distributed fault tolerance
* enterprise-grade scalability
* extensible MCP ecosystem

---

# 35. Core Philosophy

```text
Local-first
Stateful
Fault-tolerant
Distributed
Observable
Secure
Modular
Autonomous
```

---

# 36. Most Important Architectural Principle

```text
asyncio-only orchestration
                ↓
durable distributed execution platform
```

This transforms the system from:

* experimental AI workflow

into:

* production autonomous AI operating system

```
```
