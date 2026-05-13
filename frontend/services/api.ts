import {
  ResearchRequest,
  ResearchResponse,
  ResearchStatusResponse,
  MemorySearchResult,
  MemoryEntry,
  ModelProvider,
  ModelTelemetry,
  GPUStatus,
  QueueInfo,
  WorkerInfo,
  Session,
  Artifact,
  TimelineEvent,
  APIError as APIErrorType,
} from '@/types';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const API_PREFIX = process.env.NEXT_PUBLIC_API_PREFIX || '/api/v1';

class APIError extends Error {
  constructor(
    message: string,
    public statusCode: number,
    public detail?: string
  ) {
    super(message);
    this.name = 'APIError';
  }
}

export { APIError };

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error = await response.json().catch(() => ({
      error: 'An unexpected error occurred',
      status_code: response.status,
    })) as { error?: string; detail?: string; status_code?: number };
    throw new APIError(error.error || 'Request failed', response.status, error.detail);
  }
  return response.json();
}

function getHeaders(): HeadersInit {
  return {
    'Content-Type': 'application/json',
  };
}

// Research API
export const researchApi = {
  async create(request: ResearchRequest): Promise<ResearchResponse> {
    const response = await fetch(`${API_URL}${API_PREFIX}/research`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(request),
    });
    return handleResponse<ResearchResponse>(response);
  },

  async getStatus(sessionId: string): Promise<ResearchStatusResponse> {
    const response = await fetch(`${API_URL}${API_PREFIX}/research/${sessionId}/status`);
    return handleResponse<ResearchStatusResponse>(response);
  },

  async cancel(sessionId: string): Promise<{ message: string; session_id: string }> {
    const response = await fetch(`${API_URL}${API_PREFIX}/research/${sessionId}`, {
      method: 'DELETE',
    });
    return handleResponse<{ message: string; session_id: string }>(response);
  },

  async list(limit = 10, offset = 0): Promise<{ sessions: string[]; total: number; limit: number; offset: number }> {
    const response = await fetch(`${API_URL}${API_PREFIX}/research?limit=${limit}&offset=${offset}`);
    return handleResponse(response);
  },

  streamSession(sessionId: string): EventSource {
    return new EventSource(`${API_URL}${API_PREFIX}/research/${sessionId}/stream`);
  },
};

// Memory API
export const memoryApi = {
  async search(query: string, sessionId?: string, limit = 10): Promise<MemorySearchResult> {
    const response = await fetch(`${API_URL}${API_PREFIX}/memory/search`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ query, session_id: sessionId, limit }),
    });
    return handleResponse<MemorySearchResult>(response);
  },

  async getSessionMemory(sessionId: string): Promise<{ session_id: string; entries: MemoryEntry[]; total_entries: number }> {
    const response = await fetch(`${API_URL}${API_PREFIX}/memory/session/${sessionId}`);
    return handleResponse(response);
  },

  async getStats(): Promise<{ episodic_entries: number; semantic_entries: number; total_entries: number }> {
    const response = await fetch(`${API_URL}${API_PREFIX}/memory/stats`);
    return handleResponse(response);
  },

  async retrieveContext(query: string, topK = 5): Promise<{
    query: string;
    results: Array<{ content: string; score: number; source: string }>;
    context: string;
    sources: string[];
    scores: number[];
  }> {
    const response = await fetch(`${API_URL}${API_PREFIX}/memory/retrieve?query=${encodeURIComponent(query)}&top_k=${topK}`, {
      method: 'POST',
    });
    return handleResponse(response);
  },

  async getVectorStoreHealth(): Promise<{ healthy: boolean; provider: string }> {
    const response = await fetch(`${API_URL}${API_PREFIX}/memory/vector-store/health`);
    return handleResponse(response);
  },
};

// Models API
export const modelsApi = {
  async getStatus(): Promise<{
    timestamp: string;
    providers: ModelProvider[];
    gpu_status: GPUStatus;
    model_health: Record<string, { available: boolean; success_rate: number; latency_ms: number; error_count: number }>;
  }> {
    const response = await fetch(`${API_URL}${API_PREFIX}/models/status`);
    return handleResponse(response);
  },

  async getProviders(): Promise<ModelProvider[]> {
    const response = await fetch(`${API_URL}${API_PREFIX}/models/providers`);
    return handleResponse<ModelProvider[]>(response);
  },

  async testModel(provider: string, model: string, prompt = 'Hello, world!', temperature = 0.7): Promise<{
    success: boolean;
    provider: string;
    model: string;
    latency_ms: number;
    content: string;
    error?: string;
  }> {
    const response = await fetch(`${API_URL}${API_PREFIX}/models/test`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ provider, model, prompt, temperature }),
    });
    return handleResponse(response);
  },

  async getTelemetry(): Promise<ModelTelemetry> {
    const response = await fetch(`${API_URL}${API_PREFIX}/models/telemetry`);
    return handleResponse<ModelTelemetry>(response);
  },

  async getCostTelemetry(sessionId = 'default'): Promise<{
    session_id: string;
    total_cost_usd: number;
    total_tokens: number;
    by_provider: Record<string, number>;
    by_model: Record<string, number>;
  }> {
    const response = await fetch(`${API_URL}${API_PREFIX}/models/telemetry/costs?session_id=${sessionId}`);
    return handleResponse(response);
  },

  async getRoutingStats(): Promise<{
    routing_stats: Record<string, unknown>;
    circuit_breakers: Record<string, unknown>;
  }> {
    const response = await fetch(`${API_URL}${API_PREFIX}/models/routing/stats`);
    return handleResponse(response);
  },

  async getHealth(): Promise<{ healthy: boolean; providers: Record<string, boolean> }> {
    const response = await fetch(`${API_URL}${API_PREFIX}/models/health`);
    return handleResponse(response);
  },

  async getGPUStatus(): Promise<{
    available: boolean;
    mode: 'nvidia' | 'amd' | 'cpu' | 'unknown';
    status: 'available' | 'busy' | 'saturated' | 'unavailable' | 'cpu_mode' | 'error';
    gpu_count: number;
    memory: {
      total_mb: number;
      used_mb: number;
      free_mb: number;
      percent: number;
    };
    compute_utilization: number;
    temperature: number | null;
    driver_version: string | null;
    model_loaded: string | null;
    model_size_mb: number;
    is_saturated: boolean;
    is_busy: boolean;
    display_status: string;
    display_icon: string;
    last_updated: string | null;
    error: string | null;
  }> {
    const response = await fetch(`${API_URL}${API_PREFIX}/models/gpu-status`);
    return handleResponse(response);
  },

  // Model Selection API
  async getAllModels(): Promise<{
    local: Array<{
      name: string;
      provider: string;
      model_type: string;
      is_local: boolean;
      available: boolean;
      health_status: string;
      latency_ms: number;
      display_name: string;
      icon: string;
    }>;
    cloud: Record<string, Array<{
      name: string;
      provider: string;
      model_type: string;
      is_local: boolean;
      available: boolean;
      health_status: string;
      latency_ms: number;
      display_name: string;
      icon: string;
    }>>;
    timestamp: string;
  }> {
    const response = await fetch(`${API_URL}${API_PREFIX}/models`);
    return handleResponse(response);
  },

  async getLocalModels(): Promise<{
    models: Array<{
      name: string;
      provider: string;
      model_type: string;
      is_local: boolean;
      available: boolean;
      health_status: string;
      latency_ms: number;
      display_name: string;
      icon: string;
    }>;
    count: number;
    provider: string;
  }> {
    const response = await fetch(`${API_URL}${API_PREFIX}/models/local`);
    return handleResponse(response);
  },

  async getCloudModels(): Promise<{
    providers: Record<string, Array<{
      name: string;
      provider: string;
      model_type: string;
      is_local: boolean;
      available: boolean;
      health_status: string;
      latency_ms: number;
      display_name: string;
      icon: string;
    }>>;
  }> {
    const response = await fetch(`${API_URL}${API_PREFIX}/models/cloud`);
    return handleResponse(response);
  },

  async getProviderStatus(): Promise<{
    providers: Array<{
      name: string;
      provider_type: string;
      status: string;
      available: boolean;
      models: string[];
      latency_ms: number;
      error?: string;
      last_check?: string;
      status_icon: string;
    }>;
  }> {
    const response = await fetch(`${API_URL}${API_PREFIX}/models/providers/status`);
    return handleResponse(response);
  },

  async selectModel(sessionId: string, provider: string, model: string, routingMode: string): Promise<{
    success: boolean;
    provider: string;
    model: string;
    routing_mode: string;
    message: string;
    error?: string;
  }> {
    const response = await fetch(`${API_URL}${API_PREFIX}/models/select`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({
        session_id: sessionId,
        provider,
        model,
        routing_mode: routingMode,
      }),
    });
    return handleResponse(response);
  },

  async getModelSelection(sessionId: string): Promise<{
    session_id: string;
    selected_provider: string;
    selected_model: string;
    routing_mode: string;
    active_provider: string;
    active_model: string;
  }> {
    const response = await fetch(`${API_URL}${API_PREFIX}/models/selection/${sessionId}`);
    return handleResponse(response);
  },

  async refreshLocalModels(): Promise<{
    success: boolean;
    models: string[];
    count: number;
  }> {
    const response = await fetch(`${API_URL}${API_PREFIX}/models/refresh-local`, {
      method: 'POST',
    });
    return handleResponse(response);
  },
};

// Queue API
export const queueApi = {
  async getQueues(): Promise<QueueInfo[]> {
    try {
      const response = await fetch(`${API_URL}${API_PREFIX}/health/queues`);
      const data = await handleResponse<{
        timestamp: string;
        queues: Array<{
          name: string;
          status: string;
          active_tasks: number;
          pending_tasks: number;
          worker_count: number;
        }>;
        total_queues: number;
      }>(response);
      
      return data.queues.map((q) => ({
        name: q.name,
        depth: q.pending_tasks,
        active_workers: q.worker_count,
        completed_tasks: 0,
        failed_tasks: 0,
      }));
    } catch {
      // Return placeholder only if API fails
      console.warn('Queue API unavailable, using fallback data');
      return [
        { name: 'high_priority', depth: 0, active_workers: 2, completed_tasks: 0, failed_tasks: 0 },
        { name: 'research', depth: 0, active_workers: 4, completed_tasks: 0, failed_tasks: 0 },
        { name: 'browser', depth: 0, active_workers: 2, completed_tasks: 0, failed_tasks: 0 },
        { name: 'dead_letter', depth: 0, active_workers: 0, completed_tasks: 0, failed_tasks: 0 },
      ];
    }
  },

  async getWorkers(): Promise<WorkerInfo[]> {
    try {
      const response = await fetch(`${API_URL}${API_PREFIX}/health/workers`);
      const data = await handleResponse<{
        timestamp: string;
        total_workers: number;
        workers: Array<{
          name: string;
          status: string;
          active_tasks: number;
          completed_tasks: number;
          failed_tasks: number;
          uptime_seconds: number;
          last_heartbeat: string | null;
        }>;
        queues: Array<unknown>;
        overall_status: string;
      }>(response);
      
      return data.workers.map((w) => ({
        id: w.name,
        name: w.name,
        status: w.status as 'online' | 'busy' | 'offline' | 'error',
        current_task: w.active_tasks > 0 ? 'processing' : 'idle',
        started_at: w.last_heartbeat || new Date().toISOString(),
        tasks_completed: w.completed_tasks,
        tasks_failed: w.failed_tasks,
      }));
    } catch {
      console.warn('Worker API unavailable');
      return [];
    }
  },
};

// Sessions API
export const sessionsApi = {
  async getRecent(limit = 10): Promise<Session[]> {
    const response = await fetch(`${API_URL}${API_PREFIX}/research?limit=${limit}`);
    const data = await handleResponse<{ sessions: string[]; total: number }>(response);
    // Convert session IDs to Session objects (in real implementation, would fetch full session data)
    return data.sessions.map((id) => ({
      id,
      query: '',
      status: 'pending',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      progress: 0,
    }));
  },
};

// Health API
export const healthApi = {
  async check(): Promise<{ status: string; timestamp: string }> {
    const response = await fetch(`${API_URL}${API_PREFIX}/health`);
    return handleResponse(response);
  },
  
  async live(): Promise<{ status: string }> {
    const response = await fetch(`${API_URL}${API_PREFIX}/health/live`);
    return handleResponse(response);
  },
  
  async ready(): Promise<{ ready: boolean; services: Record<string, unknown> }> {
    const response = await fetch(`${API_URL}${API_PREFIX}/health/ready`);
    return handleResponse(response);
  },
  
  async workers(): Promise<{
    timestamp: string;
    total_workers: number;
    workers: Array<{
      name: string;
      status: string;
      active_tasks: number;
      completed_tasks: number;
      failed_tasks: number;
      uptime_seconds: number;
    }>;
    queues: Array<{
      name: string;
      status: string;
      active_tasks: number;
      pending_tasks: number;
      worker_count: number;
    }>;
    overall_status: string;
  }> {
    const response = await fetch(`${API_URL}${API_PREFIX}/health/workers`);
    return handleResponse(response);
  },
  
  async queues(): Promise<{
    timestamp: string;
    queues: Array<{
      name: string;
      status: string;
      active_tasks: number;
      pending_tasks: number;
      worker_count: number;
    }>;
    total_queues: number;
  }> {
    const response = await fetch(`${API_URL}${API_PREFIX}/health/queues`);
    return handleResponse(response);
  },
};

export default {
  research: researchApi,
  memory: memoryApi,
  models: modelsApi,
  queue: queueApi,
  sessions: sessionsApi,
  health: healthApi,
};