# API Reference Documentation

## Purpose

This document provides comprehensive API documentation for the AI Research Agent platform. It covers REST endpoints, WebSocket events, authentication flows, and request/response schemas. This documentation is essential for developers integrating with the platform.

---

## 1. API Overview

### Base URL

```
Production: https://api.research-agent.com
Development: http://localhost:8000
```

### API Version

```
Base Path: /api/v1
```

### Content Types

- Request: `application/json`
- Response: `application/json`

---

## 2. Authentication

### JWT Authentication

```http
Authorization: Bearer <jwt_token>
```

### Login Endpoint

```http
POST /api/v1/auth/login
```

**Request**:
```json
{
  "email": "user@example.com",
  "password": "secure_password"
}
```

**Response**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

---

## 3. Research Endpoints

### Start Research

```http
POST /api/v1/research/start
```

**Request**:
```json
{
  "query": "Research the latest developments in quantum computing",
  "max_reflections": 3,
  "options": {
    "enable_browser": true,
    "enable_github": true,
    "enable_pdf": true
  }
}
```

**Response**:
```json
{
  "session_id": "session_abc123",
  "status": "planning",
  "created_at": "2026-05-12T18:00:00Z"
}
```

### Get Session Status

```http
GET /api/v1/research/{session_id}/status
```

**Response**:
```json
{
  "session_id": "session_abc123",
  "status": "researching",
  "progress": 0.45,
  "current_agent": "router",
  "active_tasks": ["task_1", "task_2"],
  "completed_tasks": ["task_0"],
  "findings_count": 5,
  "started_at": "2026-05-12T18:00:00Z"
}
```

### Get Findings

```http
GET /api/v1/research/{session_id}/findings
```

**Response**:
```json
{
  "session_id": "session_abc123",
  "findings": [
    {
      "id": "finding_1",
      "summary": "Quantum computers use qubits instead of classical bits",
      "source": "https://example.com/quantum-computing",
      "type": "web_search",
      "collected_at": "2026-05-12T18:05:00Z"
    }
  ],
  "sources": [
    "https://example.com/quantum-computing",
    "https://arxiv.org/abs/2103.00001"
  ],
  "total": 5
}
```

### Get Final Report

```http
GET /api/v1/research/{session_id}/report
```

**Response**:
```json
{
  "session_id": "session_abc123",
  "report": "# Quantum Computing Research\n\n## Summary\n...\n## Findings\n...\n## Sources\n...",
  "word_count": 1500,
  "citations": [
    {
      "id": "cite_1",
      "source": "https://example.com",
      "format": "APA"
    }
  ],
  "completed_at": "2026-05-12T18:30:00Z"
}
```

### Cancel Research

```http
POST /api/v1/research/{session_id}/cancel
```

**Response**:
```json
{
  "session_id": "session_abc123",
  "status": "cancelled",
  "cancelled_at": "2026-05-12T18:15:00Z"
}
```

---

## 4. Memory Endpoints

### Store Memory

```http
POST /api/v1/memory
```

**Request**:
```json
{
  "content": "Research findings on quantum computing",
  "metadata": {
    "session_id": "session_abc123",
    "type": "finding",
    "tags": ["quantum", "computing"]
  }
}
```

**Response**:
```json
{
  "memory_id": "memory_xyz789",
  "created_at": "2026-05-12T18:00:00Z"
}
```

### Retrieve Memory

```http
GET /api/v1/memory?query=quantum&top_k=5
```

**Response**:
```json
{
  "memories": [
    {
      "id": "memory_xyz789",
      "content": "Research findings on quantum computing",
      "score": 0.95,
      "metadata": {
        "session_id": "session_abc123",
        "type": "finding"
      }
    }
  ]
}
```

### Search Memory

```http
POST /api/v1/memory/search
```

**Request**:
```json
{
  "query": "quantum computing breakthroughs",
  "filters": {
    "session_id": "session_abc123"
  },
  "top_k": 10
}
```

**Response**:
```json
{
  "results": [
    {
      "id": "memory_xyz789",
      "content": "...",
      "score": 0.95
    }
  ]
}
```

---

## 5. Model Endpoints

### List Available Models

```http
GET /api/v1/models
```

**Response**:
```json
{
  "models": [
    {
      "name": "qwen3",
      "provider": "ollama",
      "status": "available",
      "type": "chat"
    },
    {
      "name": "gpt-4o",
      "provider": "openai",
      "status": "available",
      "type": "chat"
    }
  ]
}
```

### Get Model Status

```http
GET /api/v1/models/{model_name}/status
```

**Response**:
```json
{
  "name": "qwen3",
  "provider": "ollama",
  "status": "available",
  "circuit_breaker": "closed",
  "last_used": "2026-05-12T18:00:00Z"
}
```

### Get Routing Stats

```http
GET /api/v1/models/routing/stats
```

**Response**:
```json
{
  "ollama": {
    "total_requests": 100,
    "successful_requests": 95,
    "failed_requests": 5,
    "fallback_count": 3,
    "avg_latency_ms": 150
  },
  "openai": {
    "total_requests": 3,
    "successful_requests": 3,
    "failed_requests": 0,
    "fallback_count": 0,
    "avg_latency_ms": 500
  }
}
```

---

## 6. Health Endpoints

### Health Check

```http
GET /api/v1/health
```

**Response**:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-05-12T18:00:00Z",
  "components": {
    "api": "healthy",
    "redis": "healthy",
    "celery": "healthy",
    "ollama": "healthy"
  }
}
```

### Detailed Health

```http
GET /api/v1/health/detailed
```

**Response**:
```json
{
  "status": "healthy",
  "api": {
    "status": "healthy",
    "uptime": 86400,
    "requests_total": 1000
  },
  "redis": {
    "status": "healthy",
    "connected_clients": 10,
    "used_memory": "50mb"
  },
  "celery": {
    "status": "healthy",
    "workers": 5,
    "active_tasks": 3
  },
  "ollama": {
    "status": "healthy",
    "models_loaded": 4
  }
}
```

---

## 7. WebSocket API

### WebSocket Connection

```
ws://api/ws/{session_id}
```

### Authentication

```javascript
// Send auth message after connection
ws.send(JSON.stringify({
  type: "auth",
  token: "jwt_token"
}));
```

### WebSocket Events

#### Outgoing Events

| Event | Description | Payload |
|-------|-------------|---------|
| start_research | Start new research | `{ query: string }` |
| cancel_research | Cancel ongoing research | `{}` |
| get_status | Request status update | `{}` |

#### Incoming Events

| Event | Description | Payload |
|-------|-------------|---------|
| workflow_update | Workflow state change | `{ status, progress, current_agent }` |
| agent_activity | Agent execution | `{ agent, action, details }` |
| finding | New finding | `{ id, summary, source, type }` |
| sources_updated | Sources updated | `{ sources: string[] }` |
| error | Error occurred | `{ error, stage }` |
| complete | Workflow complete | `{ session_id, report }` |

### WebSocket Example

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/session_abc123');

ws.onopen = () => {
  // Start research
  ws.send(JSON.stringify({
    type: 'start_research',
    query: 'Research quantum computing'
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  switch (data.type) {
    case 'workflow_update':
      console.log('Progress:', data.progress);
      break;
    case 'finding':
      console.log('New finding:', data.summary);
      break;
    case 'complete':
      console.log('Report:', data.report);
      break;
  }
};
```

---

## 8. Error Responses

### Error Format

```json
{
  "error": "error_code",
  "message": "Human readable message",
  "details": {}
}
```

### Common Errors

| Status Code | Error | Description |
|-------------|-------|-------------|
| 400 | invalid_request | Invalid request parameters |
| 401 | unauthorized | Missing or invalid authentication |
| 404 | not_found | Resource not found |
| 429 | rate_limit | Too many requests |
| 500 | internal_error | Internal server error |
| 503 | service_unavailable | Service temporarily unavailable |

---

## Related Documentation

- [System Overview](../architecture/system-overview.md)
- [Frontend Architecture](../frontend/frontend-architecture.md)
- [Observability](../observability/observability.md)