# LangGraph Workflows

## Purpose

This document provides detailed documentation of the LangGraph-based workflow orchestration system. It explains graph nodes, routing logic, reflection loops, aggregation mechanisms, and distributed execution patterns. This documentation is essential for understanding how the platform orchestrates complex multi-agent research workflows.

---

## 1. Workflow Architecture Overview

The LangGraph orchestrator manages the complete research workflow from query input to final report generation:

```mermaid
flowchart TB
    START((Start)) --> PL[Planner Agent]
    PL --> RT[Router Agent]
    RT --> DT{Dispatch Tasks?}
    DT -->|Yes| DIS[Dispatcher Node]
    DT -->|No| WR[Writer Agent]
    DIS --> PE[Parallel Execution<br/>Web, GitHub, PDF, Browser]
    PE --> AG[Aggregator Node]
    AG --> RF[Reflection Agent]
    RF --> RC{Continue<br/>Reflection?}
    RC -->|Yes| RT
    RC -->|No| WR
    WR --> END((End))
```

### Workflow Nodes

| Node | Agent/Component | Purpose |
|------|-----------------|---------|
| Planner | PlannerAgent | Decompose query into tasks |
| Router | RouterAgent | Categorize tasks, select tools |
| Dispatcher | DistributedResearchGraph | Dispatch tasks to Celery |
| Aggregator | DistributedResearchGraph | Collect and merge results |
| Reflection | ReflectionAgent | Evaluate findings, trigger research |
| Writer | WriterAgent | Generate final report |

---

## 2. Graph State Schema

The workflow maintains a comprehensive state object throughout execution:

```python
class ResearchState(TypedDict):
    # Session identification
    session_id: str
    workflow_id: str

    # Query and tasks
    query: str
    tasks: List[dict]
    active_tasks: List[str]
    completed_tasks: List[str]
    failed_tasks: List[dict]

    # Research findings
    findings: List[dict]
    sources: List[str]

    # Memory context
    memory_context: Dict

    # Reflection state
    reflections: List[str]
    reflection_count: int
    max_reflections: int

    # Report generation
    draft_report: str
    final_report: str

    # Execution tracking
    current_agent: str
    next_action: str
    status: str
    progress: float

    # Error handling
    error_state: Optional[dict]

    # Human-in-the-loop
    requires_human_input: bool

    # Observability
    token_usage: Dict[str, int]
    metadata: Dict
```

---

## 3. Node Execution Details

### 3.1 Planner Node

```mermaid
sequenceDiagram
    participant S as State
    participant P as PlannerAgent
    participant O as OllamaClient
    participant G as Graph State

    S->>P: execute(state)
    P->>O: _generate_plan(query)
    O-->>P: plan response
    P->>P: _parse_tasks(plan)
    P->>G: return {tasks, next_action, status}
```

**Responsibilities**:
- Receive user query from state
- Generate research plan using Ollama (qwen3 model)
- Parse plan into structured tasks with types
- Return updated state with task list

**Output**:
```python
{
    "tasks": [
        {"id": "task_1", "description": "...", "type": "web_search", "status": "pending"},
        {"id": "task_2", "description": "...", "type": "github_analysis", "status": "pending"}
    ],
    "next_action": "router",
    "status": "planned",
    "progress": 0.1
}
```

### 3.2 Router Node

```mermaid
sequenceDiagram
    participant S as State
    participant R as RouterAgent
    participant MCP as MCP Registry
    participant O as OllamaClient

    S->>R: execute(state)
    R->>MCP: initialize_mcp()
    R->>R: _categorize_tasks(tasks)
    loop For each task
        R->>R: _select_tools_for_task(task)
        R->>O: LLM tool selection
        O-->>R: selected tools
    end
    R->>S: return {tasks, active_tasks, tool_selections}
```

**Responsibilities**:
- Initialize MCP connection pool and registry
- Categorize tasks by type (web_search, github_analysis, pdf_analysis, browser)
- Autonomously select appropriate tools using LLM reasoning
- Add execution metadata (queue, timeout, agent)

### 3.3 Dispatcher Node

```mermaid
flowchart LR
    subgraph "Task Dispatch"
        T[Task] --> TM{Type?}
        TM -->|web_search| WS[web_search.delay]
        TM -->|github_analysis| GA[github_analysis.delay]
        TM -->|pdf_analysis| PA[pdf_analysis.delay]
        TM -->|browser| BN[browser_navigate.delay]
        WS --> CID[Correlation ID]
        GA --> CID
        PA --> CID
        BN --> CID
    end
```

**Responsibilities**:
- Iterate through all tasks in state
- Map task types to Celery task functions
- Extract parameters based on task type
- Add correlation IDs for tracking
- Dispatch to appropriate Redis queue
- Track pending tasks in internal state

### 3.4 Aggregator Node

```mermaid
sequenceDiagram
    participant S as State
    participant A as Aggregator
    participant C as Celery Results
    participant T as Task

    S->>A: execute(state)
    loop For each active_task
        A->>C: wait_for_task(celery_id, timeout)
        C-->>A: result ready
        A->>A: _extract_findings(result)
        A->>A: _extract_sources(result)
    end
    A->>A: _deduplicate_findings(findings)
    A->>A: _sum_token_usage(findings)
    A->>S: return {findings, sources, completed_tasks}
```

**Responsibilities**:
- Poll Celery results for all dispatched tasks
- Extract findings and sources from task results
- Deduplicate findings by content and source
- Sum token usage across all tasks
- Handle partial failures gracefully
- Return aggregated results

**Timeout Handling**:
- Default aggregation timeout: 120 seconds
- Tasks exceeding timeout are marked as failed
- Failed tasks are added to failed_tasks list

### 3.5 Reflection Node

```mermaid
flowchart TB
    RF[Reflection Agent] --> RC{reflection_count<br/>>= max_reflections?}
    RC -->|Yes| WR[Writer Agent]
    RC -->|No| EV[Evaluate Findings]
    EV --> QF{Sufficient<br/>Findings?}
    QF -->|Yes| WR
    QF -->|No| NT[Need More Research]
    NT --> RT[Router Agent]
```

**Responsibilities**:
- Analyze current findings for quality and completeness
- Detect potential hallucinations or inconsistencies
- Validate source credibility
- Determine if additional research is needed
- Enforce max_reflections limit (safety guardrail)

**Safety Guardrail**:
```python
def _should_continue_reflection(state):
    reflection_count = state.get("reflection_count", 0)
    max_reflections = state.get("max_reflections", 3)
    findings = state.get("findings", [])

    # Hard stop on max reflections
    if reflection_count >= max_reflections:
        return "writer"

    # Check for sufficient findings
    if len(findings) >= 5:
        return "writer"

    # Check for error state
    if state.get("error_state"):
        return "writer"

    # Continue research loop
    return "router"
```

### 3.6 Writer Node

**Responsibilities**:
- Aggregate all findings and sources
- Generate structured report with proper formatting
- Add citations and references
- Return final report in state

---

## 4. Conditional Routing

The graph uses conditional edges to determine execution flow:

### 4.1 Router → Dispatcher/Writer

```python
def _should_execute_tasks(state):
    tasks = state.get("tasks", [])
    if tasks and len(tasks) > 0:
        return "dispatch"
    return "writer"
```

### 4.2 Reflection → Router/Writer

```python
def _should_continue_reflection(state):
    # See reflection node section above
```

---

## 5. Reflection Loop

The reflection loop enables iterative research refinement:

```mermaid
flowchart TB
    subgraph "Reflection Cycle 1"
        R1[Router] --> D1[Dispatch]
        D1 --> A1[Aggregator]
        A1 --> E1[Reflection]
    end

    subgraph "Reflection Cycle 2"
        E1 --> R2[Router]
        R2 --> D2[Dispatch]
        D2 --> A2[Aggregator]
        A2 --> E2[Reflection]
    end

    subgraph "Reflection Cycle N"
        E2 --> RN[Router]
        RN --> DN[Dispatch]
        DN --> AN[Aggregator]
        AN --> EN[Reflection]
    end

    EN --> WR[Writer]
```

### Reflection Loop Behavior

1. **First Cycle**: Initial research based on planner tasks
2. **Subsequent Cycles**: Reflection agent evaluates findings, may trigger additional research
3. **Termination**: When max_reflections reached OR sufficient findings collected

### Reflection Count Enforcement

- Default max_reflections: 3
- Hard stop at limit to prevent infinite loops
- Each cycle increments reflection_count
- Metadata tracks reflection_stopped reason

---

## 6. Parallel Execution

The dispatcher sends tasks to Celery workers for parallel execution:

```mermaid
flowchart LR
    subgraph "Task Batch"
        T1[Task 1: Web Search]
        T2[Task 2: GitHub Analysis]
        T3[Task 3: PDF Analysis]
        T4[Task 4: Browser]
    end

    subgraph "Celery Queues"
        Q1[research queue]
        Q2[research queue]
        Q3[research queue]
        Q4[browser queue]
    end

    subgraph "Workers"
        W1[Worker 1]
        W2[Worker 2]
        W3[Worker 3]
        W4[Worker 4]
    end

    T1 --> Q1 --> W1
    T2 --> Q2 --> W2
    T3 --> Q3 --> W3
    T4 --> Q4 --> W4
```

### Parallel Execution Rules

- Tasks are dispatched immediately after routing
- No waiting for task completion before proceeding
- Aggregator waits for all tasks with timeout
- Partial failure is tolerated (completed tasks still used)

---

## 7. State Transitions

```mermaid
stateDiagram-v2
    [*] --> planning
    planning --> routing: tasks created
    routing --> dispatching: tasks categorized
    dispatching --> aggregating: tasks dispatched
    aggregating --> reflecting: results collected
    reflecting --> routing: need more research
    reflecting --> writing: sufficient findings
    writing --> [*]: report complete

    reflecting --> failed: error occurred
    planning --> failed: planning error
    routing --> failed: routing error
    dispatching --> failed: dispatch error
    writing --> failed: writing error
```

---

## 8. Streaming Events

The graph supports streaming events for real-time UI updates:

```python
async def stream_events(self) -> AsyncGenerator[str, None]:
    async for event in self.graph.astream(
        self.initial_state,
        config={"configurable": {"thread_id": self.session_id}},
    ):
        yield str(event)
```

### Event Types

- Node execution start
- Node execution complete
- State updates
- Error events
- Progress updates

---

## 9. Checkpointing

The graph uses MemorySaver for state persistence:

```python
checkpointer = MemorySaver()
compiled = workflow.compile(checkpointer=checkpointer)
```

**Benefits**:
- Resume interrupted workflows
- Debug state at any point
- Support long-running research tasks

---

## Related Documentation

- [System Overview](../architecture/system-overview.md)
- [Agent Architecture](../agents/agents.md)
- [Distributed Execution](../backend/distributed-execution.md)