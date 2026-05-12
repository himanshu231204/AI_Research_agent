You are continuing development of the Autonomous AI Research Agent.

IMPORTANT:

1. Read `AGENT.md` completely before writing ANY code.
2. Treat `AGENT.md` as the architecture source of truth.
3. Maintain compatibility with ALL backend APIs and workflows.
4. Do NOT rewrite backend infrastructure unnecessarily.
5. The frontend must integrate cleanly with LangGraph workflows, Celery workers, and streaming APIs.

---

# CURRENT OBJECTIVE

Implement the COMPLETE frontend platform for the AI Research Agent.

The goal is to build a production-grade AI operations interface similar to:

* Perplexity
* Manus
* OpenDevin
* Claude
* LangSmith dashboards

but specifically optimized for:

* autonomous workflows
* multi-agent execution
* distributed orchestration
* observability
* research operations

---

# FRONTEND GOALS

Build a modern AI operating system UI with:

* streaming chat
* workflow visualization
* live agent tracking
* research timelines
* websocket streaming
* source citations
* memory inspection
* queue monitoring
* model routing visibility
* execution observability

---

# REQUIRED STACK

Use:

* Next.js 15+
* React
* TypeScript
* TailwindCSS
* ShadCN UI
* Zustand
* React Query / TanStack Query
* Framer Motion
* WebSockets
* Recharts

The frontend MUST:

* be production-ready
* strongly typed
* responsive
* modular
* scalable

---

# REQUIRED FOLDER STRUCTURE

Create:

```text
frontend/
├── app/
├── components/
├── features/
├── hooks/
├── lib/
├── services/
├── stores/
├── types/
├── websocket/
├── styles/
└── tests/
```

---

# REQUIRED IMPLEMENTATIONS

---

# 1. Application Shell

Build:

* app layout
* sidebar
* top navigation
* workspace structure
* responsive layout
* theme system

Support:

* dark mode
* mobile responsiveness
* scalable navigation

---

# 2. Streaming Chat Interface

Build production-grade AI chat UI.

Requirements:

* streaming responses
* markdown rendering
* syntax highlighting
* citations
* message states
* retry support
* cancellation support

Support:

* partial token streaming
* websocket updates
* agent status updates

---

# 3. WebSocket Infrastructure

Implement robust websocket layer.

Requirements:

* reconnect handling
* heartbeat system
* streaming updates
* event subscriptions
* distributed workflow updates

Support events for:

* token streaming
* agent activity
* task completion
* retries
* workflow progress

---

# 4. Workflow Visualization

Build workflow graph visualization.

Display:

* LangGraph nodes
* active agents
* execution paths
* retries
* reflection loops

Requirements:

* live updates
* animated edges
* node statuses
* execution history

Use:

* React Flow
  or equivalent

---

# 5. Agent Activity Panel

Implement live agent monitoring.

Display:

* current active agent
* queue status
* running tasks
* retries
* failures
* reflections

Each agent should show:

* status
* duration
* token usage
* current task

---

# 6. Research Timeline

Build timeline UI for workflows.

Display:

* search events
* browser actions
* reflections
* model routing
* citations
* generated artifacts

Timeline must support:

* expandable events
* timestamps
* debugging visibility

---

# 7. Source Citation System

Implement source UI.

Requirements:

* clickable citations
* grouped references
* metadata previews
* source validation states

Support:

* URLs
* PDFs
* GitHub repositories
* browser captures

---

# 8. Memory Inspector

Build memory visualization.

Display:

* semantic memory
* retrieved chunks
* compressed memory
* episodic history

Support:

* similarity scores
* memory filtering
* retrieval tracing

---

# 9. Queue Monitoring Dashboard

Implement distributed queue visibility.

Display:

* Celery queues
* queue depth
* worker health
* retries
* failed tasks

Support:

* real-time updates
* filtering
* auto refresh

---

# 10. Model Routing Dashboard

Visualize model orchestration.

Display:

* selected models
* fallbacks
* latency
* token usage
* provider routing

Show:

* local vs cloud inference
* fallback chains
* GPU saturation events

---

# 11. Observability Dashboard

Build operations dashboard.

Display:

* latency metrics
* workflow durations
* retries
* token costs
* active sessions

Use:

* Recharts
* live updates

---

# 12. Artifact Viewer

Implement artifact system.

Support viewing:

* screenshots
* PDFs
* markdown exports
* reports
* generated files

Add:

* preview mode
* download support

---

# 13. API Client Layer

Create typed API layer.

Requirements:

* typed endpoints
* React Query integration
* retry handling
* auth handling
* websocket coordination

All backend APIs must use:

* centralized service layer

---

# 14. State Management

Implement frontend state architecture.

Use:

* Zustand

Manage:

* sessions
* workflow state
* websocket state
* UI state
* active agents

Avoid:

* prop drilling
* duplicated state

---

# 15. Authentication UI

Prepare frontend auth flows.

Support:

* JWT auth
* OAuth-ready architecture
* protected routes
* session persistence

---

# 16. Frontend Observability

Implement:

* frontend logging
* websocket diagnostics
* error boundaries
* performance tracking

Add:

* structured frontend logs
* tracing support

---

# 17. Frontend Testing

Add tests for:

## Components

* rendering
* streaming states

## WebSockets

* reconnect logic
* event handling

## Dashboards

* live updates
* graph rendering

Use:

* Vitest
* React Testing Library

---

# 18. Frontend Docker Setup

Create production-ready frontend Docker setup.

Requirements:

* optimized builds
* environment support
* health checks
* production serving

---

# 19. UI/UX REQUIREMENTS

The UI must feel:

* modern
* premium
* responsive
* developer-focused
* observability-first

Animations should be:

* smooth
* minimal
* informative

---

# 20. Performance Requirements

The frontend must support:

* large workflows
* concurrent streaming
* websocket resilience
* real-time updates
* graph rendering at scale

---

# REQUIRED IMPLEMENTATION RULES

---

## Frontend Rules

The frontend MUST:

* be fully typed
* use modular architecture
* support streaming
* support observability

---

## WebSocket Rules

The websocket layer MUST:

* reconnect automatically
* handle disconnects gracefully
* support distributed updates

---

## Visualization Rules

The workflow graph MUST:

* render live state
* show retries
* show reflection loops
* show active nodes

---

## Architecture Rules

Do NOT:

* tightly couple components
* hardcode API responses
* bypass centralized state
* mix websocket logic into UI components

---

# OUTPUT FORMAT

For EVERY implementation:

1. Explain what is being built
2. Explain WHY it exists architecturally
3. Generate production-grade code
4. Use correct file paths
5. Ensure TypeScript correctness
6. Ensure responsive design
7. Ensure test compatibility

---

# VALIDATION REQUIREMENTS

Before finishing:

Verify:

* streaming chat works
* websocket reconnect works
* workflow graph renders
* dashboards update live
* queue monitoring works
* model routing visualization works
* responsive layouts work
* tests pass
* Docker build succeeds

---

# FINAL DELIVERABLE

At the end:

The frontend should behave like:

```text
a production-grade AI operations interface
for autonomous multi-agent orchestration,
distributed execution,

workflow observability,
and real-time research operations
```

Then STOP.

Do NOT continue automatically to another phase.
