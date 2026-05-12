import { useWSStore, useResearchStore, useAgentsStore, useTimelineStore, useChatStore } from '@/stores';
import type { WSMessageType, ResearchUpdatePayload, AgentActivityPayload, TokenStreamPayload } from '@/types';

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';

type MessageHandler = (payload: unknown) => void;

class WebSocketService {
  private ws: WebSocket | null = null;
  private sessionId: string | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private heartbeatInterval: NodeJS.Timeout | null = null;
  private handlers: Map<WSMessageType, Set<MessageHandler>> = new Map();
  private isIntentionalClose = false;

  connect(sessionId: string): void {
    if (this.ws?.readyState === WebSocket.OPEN && this.sessionId === sessionId) {
      return;
    }

    this.sessionId = sessionId;
    this.isIntentionalClose = false;

    try {
      this.ws = new WebSocket(`${WS_URL}/ws/${sessionId}`);
      this.setupEventHandlers();
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
      useWSStore.getState().setConnected(true);
      useWSStore.getState().setConnectionError(null);
      this.reconnectAttempts = 0;
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
      useWSStore.getState().setConnected(false);
      this.stopHeartbeat();

      if (!this.isIntentionalClose) {
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
    }

    // Call registered handlers
    const handlers = this.handlers.get(type as WSMessageType);
    if (handlers) {
      handlers.forEach((handler) => handler(payload));
    }
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
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached');
      useWSStore.getState().setConnectionError('Max reconnection attempts reached');
      return;
    }

    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts);
    console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts + 1})`);
    
    setTimeout(() => {
      this.reconnectAttempts++;
      if (this.sessionId) {
        this.connect(this.sessionId);
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