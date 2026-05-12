// Research Types
export interface ResearchRequest {
  query: string;
  max_reflections?: number;
  session_id?: string;
}

export interface ResearchResponse {
  session_id: string;
  status: string;
  message: string;
}

export interface ResearchStatusResponse {
  session_id: string;
  status: ResearchStatus;
  progress: number;
  current_agent?: string;
  completed_tasks: string[];
  findings: ResearchFinding[];
  draft_report?: string;
  final_report?: string;
  error?: string;
}

export type ResearchStatus = 
  | 'pending'
  | 'planning'
  | 'researching'
  | 'reflecting'
  | 'writing'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'running';

export interface ResearchFinding {
  id: string;
  source: string;
  content: string;
  timestamp: string;
  relevance?: number;
}

// Message Types
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  status?: MessageStatus;
  sources?: Citation[];
  metadata?: Record<string, unknown>;
}

export type MessageStatus = 'streaming' | 'completed' | 'error' | 'cancelled';

export interface Citation {
  id: string;
  type: CitationType;
  url?: string;
  title?: string;
  snippet?: string;
  metadata?: Record<string, unknown>;
}

export type CitationType = 'web' | 'pdf' | 'github' | 'browser' | 'memory';

// Agent Types
export interface Agent {
  id: string;
  name: AgentName;
  status: AgentStatus;
  current_task?: string;
  started_at?: string;
  duration_ms?: number;
  token_usage?: TokenUsage;
  metadata?: Record<string, unknown>;
}

export type AgentName = 
  | 'planner'
  | 'task_router'
  | 'web_research'
  | 'github_analysis'
  | 'pdf_rag'
  | 'browser_automation'
  | 'memory'
  | 'reflection'
  | 'writer'
  | 'citation';

export type AgentStatus = 'idle' | 'running' | 'completed' | 'failed' | 'waiting';

export interface TokenUsage {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cost_usd?: number;
}

// Workflow Types
export interface WorkflowNode {
  id: string;
  name: string;
  type: AgentName;
  status: AgentStatus;
  position: { x: number; y: number };
  inputs?: Record<string, unknown>;
  outputs?: Record<string, unknown>;
  started_at?: string;
  completed_at?: string;
  duration_ms?: number;
}

export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  type: EdgeType;
  animated?: boolean;
}

export type EdgeType = 'default' | 'reflection' | 'retry' | 'fallback';

export interface WorkflowState {
  session_id: string;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  current_node?: string;
  progress: number;
  status: ResearchStatus;
}

// Memory Types
export interface MemoryEntry {
  id: string;
  type: MemoryType;
  content: string;
  session_id: string;
  timestamp: string;
  embedding?: number[];
  metadata?: Record<string, unknown>;
  similarity?: number;
}

export type MemoryType = 'semantic' | 'episodic' | 'working' | 'compressed';

export interface MemorySearchResult {
  query: string;
  entries: MemoryEntry[];
  total_found: number;
  retrieval_time_ms: number;
  cache_hit: boolean;
}

// Queue Types
export interface QueueInfo {
  name: string;
  depth: number;
  active_workers: number;
  completed_tasks: number;
  failed_tasks: number;
  avg_wait_time_ms?: number;
}

export interface WorkerInfo {
  id: string;
  name: string;
  status: WorkerStatus;
  current_task?: string;
  started_at?: string;
  tasks_completed: number;
  tasks_failed: number;
}

export type WorkerStatus = 'online' | 'busy' | 'offline' | 'error';

// Model Types
export interface ModelProvider {
  name: string;
  type: 'local' | 'cloud';
  status: ProviderStatus;
  available: boolean;
  models: string[];
  latency_ms: number;
  circuit_breaker?: CircuitBreakerStatus;
}

export type ProviderStatus = 'healthy' | 'degraded' | 'unhealthy' | 'unavailable';

export interface CircuitBreakerStatus {
  state: 'closed' | 'open' | 'half_open';
  failure_count: number;
  last_failure?: string;
}

export interface GPUStatus {
  available: boolean;
  mode?: 'nvidia' | 'amd' | 'cpu' | 'unknown';
  status?: 'available' | 'busy' | 'saturated' | 'unavailable' | 'cpu_mode' | 'error';
  gpu_count?: number;
  memory?: {
    total_mb: number;
    used_mb: number;
    free_mb: number;
    percent: number;
  };
  memory_percent?: number; // Legacy support
  compute_utilization?: number;
  temperature?: number;
  driver_version?: string;
  model_loaded?: string;
  model_size_mb?: number;
  is_saturated?: boolean;
  is_busy?: boolean;
  active_models?: string[]; // Legacy support
  display_status?: string;
  display_icon?: string;
  last_updated?: string;
  error?: string;
}

export interface ModelTelemetry {
  summary: TelemetrySummary;
  providers: Record<string, ProviderTelemetry>;
  task_types: Record<string, TaskTypeTelemetry>;
}

export interface TelemetrySummary {
  total_requests: number;
  total_tokens: number;
  total_cost_usd: number;
  avg_latency_ms: number;
  success_rate: number;
}

export interface ProviderTelemetry {
  requests: number;
  tokens: number;
  cost_usd: number;
  latency_ms: number;
  success_rate: number;
}

export interface TaskTypeTelemetry {
  requests: number;
  avg_latency_ms: number;
  success_rate: number;
}

// WebSocket Types
export interface WSMessage {
  type: WSMessageType;
  payload: unknown;
}

export type WSMessageType = 
  | 'research_update'
  | 'agent_activity'
  | 'token_stream'
  | 'research_complete'
  | 'error'
  | 'pong'
  | 'subscribe'
  | 'unsubscribe';

export interface ResearchUpdatePayload {
  session_id: string;
  status: ResearchStatus;
  progress: number;
  current_agent?: string;
  node_id?: string;
  message?: string;
}

export interface AgentActivityPayload {
  agent: AgentName;
  activity: string;
  timestamp: string;
  metadata?: Record<string, unknown>;
}

export interface TokenStreamPayload {
  session_id: string;
  token: string;
  agent?: AgentName;
}

// UI State Types
export interface UIState {
  theme: 'light' | 'dark' | 'system';
  sidebarOpen: boolean;
  activePanel?: PanelType;
  selectedSessionId?: string;
}

export type PanelType = 
  | 'chat'
  | 'workflow'
  | 'agents'
  | 'memory'
  | 'queue'
  | 'models'
  | 'observability'
  | 'artifacts';

// Session Types
export interface Session {
  id: string;
  query: string;
  status: ResearchStatus;
  created_at: string;
  updated_at: string;
  progress: number;
  current_agent?: string;
}

// Artifact Types
export interface Artifact {
  id: string;
  type: ArtifactType;
  name: string;
  url?: string;
  content?: string;
  session_id: string;
  created_at: string;
  metadata?: Record<string, unknown>;
}

export type ArtifactType = 
  | 'screenshot'
  | 'pdf'
  | 'markdown'
  | 'report'
  | 'code'
  | 'data';

// Timeline Types
export interface TimelineEvent {
  id: string;
  type: TimelineEventType;
  agent?: AgentName;
  message: string;
  timestamp: string;
  metadata?: Record<string, unknown>;
}

export type TimelineEventType = 
  | 'search'
  | 'browser_action'
  | 'reflection'
  | 'model_routing'
  | 'citation'
  | 'artifact'
  | 'error'
  | 'task_start'
  | 'task_complete';

// API Error Types
export interface APIError {
  error: string;
  detail?: string;
  status_code: number;
}

// Auth Types
export interface AuthUser {
  id: string;
  email: string;
  name?: string;
  avatar?: string;
}

export interface AuthState {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}