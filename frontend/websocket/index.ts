import { useWSStore, useResearchStore, useAgentsStore, useTimelineStore, useChatStore, useModelSelectionStore } from '@/stores';
import type { WSMessageType, ResearchUpdatePayload, AgentActivityPayload, TokenStreamPayload } from '@/types';

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';
const WS_PREFIX = '/ws';

// Reconnection configuration
const MAX_RECONNECT_ATTEMPTS = 10;
const INITIAL_RECONNECT_DELAY = 1000;
const MAX_RECONNECT_DELAY = 30000;
const RECONNECT_JITTER = 0.3; // 30% jitter
const HEARTBEAT_INTERVAL = 30000;
const CONNECTION_TIMEOUT = 10000;

type MessageHandler = (payload: unknown) => void;

class WebSocketService {
  private ws: WebSocket | null = null;
  private sessionId: string | null = null;
  private authToken: string | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = MAX_RECONNECT_ATTEMPTS;
  private reconnectDelay = INITIAL_RECONNECT_DELAY;
  private heartbeatInterval: NodeJS.Timeout | null = null;
  private connectionTimeout: NodeJS.Timeout | null = null;
  private handlers: Map<WSMessageType, Set<MessageHandler>> = new Map();
  private isIntentionalClose = false;
  private isReconnecting = false;

  /**
   * Connect to WebSocket with optional authentication token.
   * 
   * @param sessionId - The session ID for the connection
   * @param token - Optional JWT token for authentication
   */
  connect(sessionId: string, token?: string): void {
    // Close existing connection if session ID changed
    if (this.ws && this.sessionId !== sessionId) {
      this.disconnect();
    }

    // Don't reconnect if already connected to the right session
    if (this.ws?.readyState === WebSocket.OPEN && this.sessionId === sessionId) {
      return;
    }

    this.sessionId = sessionId;
    this.authToken = token || null;
    this.isIntentionalClose = false;

    try {
      // Build WebSocket URL with optional token
      let wsUrl = `${WS_URL}${WS_PREFIX}/${sessionId}`;
      if (this.authToken) {
        wsUrl += `?token=${encodeURIComponent(this.authToken)}`;
      }
      console.log(`[WebSocket] Connecting to: ${wsUrl}`);
      
      this.ws = new WebSocket(wsUrl);
      this.setupEventHandlers();
      
      // Set connection timeout
      this.connectionTimeout = setTimeout(() => {
        if (this.ws?.readyState !== WebSocket.OPEN) {
          console.warn('[WebSocket] Connection timeout, closing...');
          this.ws?.close();
        }
      }, CONNECTION_TIMEOUT);
      
    } catch (error) {
      console.error('WebSocket connection error:', error);
      useWSStore.getState().setConnectionError('Failed to connect');
      this.scheduleReconnect();
    }
  }

  private setupEventHandlers(): void {
    if (!this.ws) return;

    this.ws.onopen = () => {
      console.log('WebSocket connected');
      
      // Clear connection timeout
      if (this.connectionTimeout) {
        clearTimeout(this.connectionTimeout);
        this.connectionTimeout = null;
      }
      
      useWSStore.getState().setConnected(true);
      useWSStore.getState().setConnectionError(null);
      this.reconnectAttempts = 0;
      this.reconnectDelay = INITIAL_RECONNECT_DELAY; // Reset delay on successful connection
      this.isReconnecting = false;
      this.startHeartbeat();
    };

    this.ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        this.handleMessage(message);
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };

    this.ws.onclose = (event) => {
      console.log('WebSocket closed:', event.code, event.reason);
      
      // Clear connection timeout
      if (this.connectionTimeout) {
        clearTimeout(this.connectionTimeout);
        this.connectionTimeout = null;
      }
      
      useWSStore.getState().setConnected(false);
      this.stopHeartbeat();

      // Don't reconnect on normal closure or intentional close
      if (!this.isIntentionalClose && event.code !== 1000) {
        this.scheduleReconnect();
      }
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      useWSStore.getState().setConnectionError('Connection error');
    };
  }

  private handleMessage(message: { type: string; payload: unknown }): void {
    const { type, payload } = message;
    useWSStore.getState().setLastMessage(message);

    // Handle built-in message types
    switch (type) {
      case 'research_update':
        this.handleResearchUpdate(payload as ResearchUpdatePayload);
        break;
      case 'agent_activity':
        this.handleAgentActivity(payload as AgentActivityPayload);
        break;
      case 'token_stream':
        this.handleTokenStream(payload as TokenStreamPayload);
        break;
      case 'research_complete':
        this.handleResearchComplete(payload as { report: string });
        break;
      case 'error':
        console.error('Server error:', payload);
        break;
      case 'pong':
        // Heartbeat response
        break;
      
      // Model selection events
      case 'model_update':
        this.handleModelUpdate(payload as {
          selected_provider: string;
          selected_model: string;
          routing_mode: string;
          active_provider: string;
          active_model: string;
        });
        break;
      case 'fallback_event':
        this.handleFallbackEvent(payload as {
          from_provider: string;
          from_model: string;
          to_provider: string;
          to_model: string;
          reason: string;
        });
        break;
      case 'provider_status_change':
        this.handleProviderStatusChange(payload as {
          provider: string;
          status: string;
          available: boolean;
        });
        break;
      case 'models_refreshed':
        this.handleModelsRefreshed(payload as {
          local: unknown[];
          cloud: Record<string, unknown[]>;
        });
        break;
    }

    // Call registered handlers
    const handlers = this.handlers.get(type as WSMessageType);
    if (handlers) {
      handlers.forEach((handler) => handler(payload));
    }
  }

  private handleModelUpdate(payload: {
    selected_provider: string;
    selected_model: string;
    routing_mode: string;
    active_provider: string;
    active_model: string;
  }): void {
    const store = useModelSelectionStore.getState();
    store.setSelectedProvider(payload.selected_provider);
    store.setSelectedModel(payload.selected_model);
    store.setRoutingMode(payload.routing_mode);
    store.setActiveModelInfo(payload.active_provider, payload.active_model);
  }

  private handleFallbackEvent(payload: {
    from_provider: string;
    from_model: string;
    to_provider: string;
    to_model: string;
    reason: string;
  }): void {
    const store = useModelSelectionStore.getState();
    store.setFallbackInfo(true, payload.reason);
    store.setActiveModelInfo(payload.to_provider, payload.to_model);
    
    // Add timeline event
    useTimelineStore.getState().addEvent({
      id: `event-${Date.now()}`,
      type: 'model_routing',
      message: `Fallback: ${payload.from_provider}/${payload.from_model} → ${payload.to_provider}/${payload.to_model} (${payload.reason})`,
      timestamp: new Date().toISOString(),
    });
  }

  private handleProviderStatusChange(payload: {
    provider: string;
    status: string;
    available: boolean;
  }): void {
    // Refresh provider status
    const store = useModelSelectionStore.getState();
    const currentStatuses = store.providerStatuses;
    
    const updatedStatuses = currentStatuses.map(s => 
      s.name === payload.provider
        ? { ...s, status: payload.status, available: payload.available }
        : s
    );
    
    store.setProviderStatuses(updatedStatuses);
  }

  private handleModelsRefreshed(payload: {
    local: unknown[];
    cloud: Record<string, unknown[]>;
  }): void {
    const store = useModelSelectionStore.getState();
    store.setLocalModels(payload.local as never[]);
    store.setCloudModels(payload.cloud as Record<string, never[]>);
  }

  private handleResearchUpdate(payload: ResearchUpdatePayload): void {
    const { status, progress, current_agent, message } = payload;
    
    useResearchStore.getState().setStatus(status);
    useResearchStore.getState().setProgress(progress);
    if (current_agent) {
      useResearchStore.getState().setCurrentAgent(current_agent);
    }

    // Add timeline event
    if (message) {
      useTimelineStore.getState().addEvent({
        id: `event-${Date.now()}`,
        type: 'task_start',
        agent: current_agent as any,
        message,
        timestamp: new Date().toISOString(),
      });
    }
  }

  private handleAgentActivity(payload: AgentActivityPayload): void {
    const { agent, activity, timestamp, metadata } = payload;
    
    // Update agent status
    const agentsStore = useAgentsStore.getState();
    const existingAgent = agentsStore.agents.find((a) => a.name === agent);
    
    if (existingAgent) {
      agentsStore.updateAgent(existingAgent.id, {
        status: 'running',
        current_task: activity,
        started_at: timestamp,
      });
    }

    // Add timeline event
    useTimelineStore.getState().addEvent({
      id: `event-${Date.now()}`,
      type: 'task_start',
      agent,
      message: activity,
      timestamp,
      metadata,
    });
  }

  private handleTokenStream(payload: TokenStreamPayload): void {
    const { token, agent } = payload;
    
    // Append to streaming content
    useChatStore.getState().appendStreamingContent(token);
  }

  private handleResearchComplete(payload: { report: string }): void {
    const { report } = payload;
    
    useResearchStore.getState().setStatus('completed');
    useResearchStore.getState().setProgress(1);
    useResearchStore.getState().setFinalReport(report);
    useChatStore.getState().setStreaming(false);
  }

  private startHeartbeat(): void {
    this.heartbeatInterval = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.send({ type: 'ping', payload: {} });
      }
    }, 30000);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  private scheduleReconnect(): void {
    // Prevent multiple simultaneous reconnection attempts
    if (this.isReconnecting) {
      return;
    }
    
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached');
      useWSStore.getState().setConnectionError('Max reconnection attempts reached. Please refresh the page.');
      return;
    }

    this.isReconnecting = true;
    
    // Calculate delay with exponential backoff and jitter
    const baseDelay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts);
    const jitter = baseDelay * RECONNECT_JITTER * Math.random();
    const delay = Math.min(baseDelay + jitter, MAX_RECONNECT_DELAY);
    
    console.log(`[WebSocket] Reconnecting in ${Math.round(delay)}ms (attempt ${this.reconnectAttempts + 1}/${this.maxReconnectAttempts})`);
    
    setTimeout(() => {
      this.reconnectAttempts++;
      if (this.sessionId) {
        this.connect(this.sessionId, this.authToken || undefined);
      }
    }, delay);
  }

  send(message: { type: string; payload: unknown }): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket not connected, cannot send message');
    }
  }

  subscribe(handler: MessageHandler, messageType: WSMessageType): () => void {
    if (!this.handlers.has(messageType)) {
      this.handlers.set(messageType, new Set());
    }
    this.handlers.get(messageType)!.add(handler);

    // Return unsubscribe function
    return () => {
      this.handlers.get(messageType)?.delete(handler);
    };
  }

  disconnect(): void {
    this.isIntentionalClose = true;
    this.stopHeartbeat();
    
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    
    this.sessionId = null;
    useWSStore.getState().setConnected(false);
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  get currentSessionId(): string | null {
    return this.sessionId;
  }
}

// Singleton instance
export const wsService = new WebSocketService();

// React hook for WebSocket
export function useWebSocket(sessionId: string | null) {
  // This would be used in components to connect/disconnect
  return {
    connect: () => sessionId && wsService.connect(sessionId),
    disconnect: () => wsService.disconnect(),
    send: (message: { type: string; payload: unknown }) => wsService.send(message),
    isConnected: wsService.isConnected,
  };
}

export default wsService;