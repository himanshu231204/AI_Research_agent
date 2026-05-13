import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import {
  ChatMessage,
  ResearchStatus,
  Agent,
  WorkflowState,
  UIState,
  Session,
  TimelineEvent,
  Citation,
} from '@/types';

// Model types for model selection
interface ModelInfo {
  name: string;
  provider: string;
  model_type: string;
  is_local: boolean;
  available: boolean;
  health_status: string;
  latency_ms: number;
  display_name: string;
  icon: string;
}

interface ProviderStatus {
  name: string;
  provider_type: string;
  status: string;
  available: boolean;
  models: string[];
  latency_ms: number;
  error?: string;
  status_icon: string;
}

// UI Store
interface UIStore extends UIState {
  setTheme: (theme: 'light' | 'dark' | 'system') => void;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  setActivePanel: (panel: UIState['activePanel']) => void;
  setSelectedSessionId: (sessionId: string | undefined) => void;
}

export const useUIStore = create<UIStore>()(
  immer((set) => ({
    theme: 'dark',
    sidebarOpen: true,
    activePanel: 'chat',
    setTheme: (theme) => set({ theme }),
    toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
    setSidebarOpen: (open) => set({ sidebarOpen: open }),
    setActivePanel: (panel) => set({ activePanel: panel }),
    setSelectedSessionId: (sessionId) => set({ selectedSessionId: sessionId }),
  }))
);

// Chat Store
interface ChatStore {
  messages: ChatMessage[];
  currentSessionId: string | null;
  isStreaming: boolean;
  streamingContent: string;
  
  addMessage: (message: ChatMessage) => void;
  updateMessage: (id: string, updates: Partial<ChatMessage>) => void;
  appendStreamingContent: (content: string) => void;
  setStreaming: (isStreaming: boolean) => void;
  setCurrentSessionId: (sessionId: string | null) => void;
  clearMessages: () => void;
}

export const useChatStore = create<ChatStore>()(
  immer((set) => ({
    messages: [],
    currentSessionId: null,
    isStreaming: false,
    streamingContent: '',
    
    addMessage: (message) =>
      set((state) => {
        state.messages.push(message);
      }),
    
    updateMessage: (id, updates) =>
      set((state) => {
        const index = state.messages.findIndex((m) => m.id === id);
        if (index !== -1) {
          state.messages[index] = { ...state.messages[index], ...updates };
        }
      }),
    
    appendStreamingContent: (content) =>
      set((state) => {
        state.streamingContent += content;
      }),
    
    setStreaming: (isStreaming) =>
      set((state) => {
        state.isStreaming = isStreaming;
        if (!isStreaming && state.streamingContent) {
          // Add the final message when streaming completes
          state.messages.push({
            id: `msg-${Date.now()}`,
            role: 'assistant',
            content: state.streamingContent,
            timestamp: new Date().toISOString(),
            status: 'completed',
          });
          state.streamingContent = '';
        }
      }),
    
    setCurrentSessionId: (sessionId) =>
      set((state) => {
        state.currentSessionId = sessionId;
      }),
    
    clearMessages: () =>
      set((state) => {
        state.messages = [];
        state.streamingContent = '';
        state.isStreaming = false;
      }),
  }))
);

// Research Store
interface ResearchStore {
  currentSessionId: string | null;
  status: ResearchStatus;
  progress: number;
  currentAgent: string | null;
  completedTasks: string[];
  findings: Array<{ id: string; source: string; content: string }>;
  draftReport: string | null;
  finalReport: string | null;
  error: string | null;
  
  setSessionId: (sessionId: string | null) => void;
  setStatus: (status: ResearchStatus) => void;
  setProgress: (progress: number) => void;
  setCurrentAgent: (agent: string | null) => void;
  addCompletedTask: (task: string) => void;
  addFinding: (finding: { id: string; source: string; content: string }) => void;
  setDraftReport: (report: string | null) => void;
  setFinalReport: (report: string | null) => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

export const useResearchStore = create<ResearchStore>()(
  immer((set) => ({
    currentSessionId: null,
    status: 'pending',
    progress: 0,
    currentAgent: null,
    completedTasks: [],
    findings: [],
    draftReport: null,
    finalReport: null,
    error: null,
    
    setSessionId: (sessionId) => set({ currentSessionId: sessionId }),
    setStatus: (status) => set({ status }),
    setProgress: (progress) => set({ progress }),
    setCurrentAgent: (agent) => set({ currentAgent: agent }),
    addCompletedTask: (task) =>
      set((state) => {
        state.completedTasks.push(task);
      }),
    addFinding: (finding) =>
      set((state) => {
        state.findings.push(finding);
      }),
    setDraftReport: (report) => set({ draftReport: report }),
    setFinalReport: (report) => set({ finalReport: report }),
    setError: (error) => set({ error }),
    reset: () =>
      set({
        currentSessionId: null,
        status: 'pending',
        progress: 0,
        currentAgent: null,
        completedTasks: [],
        findings: [],
        draftReport: null,
        finalReport: null,
        error: null,
      }),
  }))
);

// Agents Store
interface AgentsStore {
  agents: Agent[];
  activeAgent: string | null;
  
  setAgents: (agents: Agent[]) => void;
  updateAgent: (id: string, updates: Partial<Agent>) => void;
  setActiveAgent: (agentId: string | null) => void;
}

export const useAgentsStore = create<AgentsStore>()(
  immer((set) => ({
    agents: [],
    activeAgent: null,
    
    setAgents: (agents) => set({ agents }),
    updateAgent: (id, updates) =>
      set((state) => {
        const index = state.agents.findIndex((a) => a.id === id);
        if (index !== -1) {
          state.agents[index] = { ...state.agents[index], ...updates };
        }
      }),
    setActiveAgent: (agentId) => set({ activeAgent: agentId }),
  }))
);

// Workflow Store
interface WorkflowStore {
  workflow: WorkflowState;
  
  setWorkflow: (workflow: WorkflowState) => void;
  updateNode: (nodeId: string, updates: Partial<WorkflowState['nodes'][0]>) => void;
  addEdge: (edge: WorkflowState['edges'][0]) => void;
  setCurrentNode: (nodeId: string | undefined) => void;
  setProgress: (progress: number) => void;
  setStatus: (status: ResearchStatus) => void;
  reset: () => void;
}

const initialWorkflowState: WorkflowState = {
  session_id: '',
  nodes: [],
  edges: [],
  progress: 0,
  status: 'pending',
};

export const useWorkflowStore = create<WorkflowStore>()(
  immer((set) => ({
    workflow: initialWorkflowState,
    
    setWorkflow: (workflow) => set({ workflow }),
    updateNode: (nodeId, updates) =>
      set((state) => {
        const index = state.workflow.nodes.findIndex((n) => n.id === nodeId);
        if (index !== -1) {
          state.workflow.nodes[index] = { ...state.workflow.nodes[index], ...updates };
        }
      }),
    addEdge: (edge) =>
      set((state) => {
        state.workflow.edges.push(edge);
      }),
    setCurrentNode: (nodeId) =>
      set((state) => {
        state.workflow.current_node = nodeId;
      }),
    setProgress: (progress) =>
      set((state) => {
        state.workflow.progress = progress;
      }),
    setStatus: (status) =>
      set((state) => {
        state.workflow.status = status;
      }),
    reset: () => set({ workflow: initialWorkflowState }),
  }))
);

// Timeline Store
interface TimelineStore {
  events: TimelineEvent[];
  
  addEvent: (event: TimelineEvent) => void;
  clearEvents: () => void;
}

export const useTimelineStore = create<TimelineStore>()(
  immer((set) => ({
    events: [],
    
    addEvent: (event) =>
      set((state) => {
        state.events.push(event);
      }),
    clearEvents: () => set({ events: [] }),
  }))
);

// Sessions Store
interface SessionsStore {
  sessions: Session[];
  isLoading: boolean;
  
  setSessions: (sessions: Session[]) => void;
  addSession: (session: Session) => void;
  updateSession: (id: string, updates: Partial<Session>) => void;
  setLoading: (loading: boolean) => void;
}

export const useSessionsStore = create<SessionsStore>()(
  immer((set) => ({
    sessions: [],
    isLoading: false,
    
    setSessions: (sessions) => set({ sessions }),
    addSession: (session) =>
      set((state) => {
        state.sessions.unshift(session);
      }),
    updateSession: (id, updates) =>
      set((state) => {
        const index = state.sessions.findIndex((s) => s.id === id);
        if (index !== -1) {
          state.sessions[index] = { ...state.sessions[index], ...updates };
        }
      }),
    setLoading: (loading) => set({ isLoading: loading }),
  }))
);

// WebSocket Store
interface WSStore {
  isConnected: boolean;
  lastMessage: unknown | null;
  connectionError: string | null;
  
  setConnected: (connected: boolean) => void;
  setLastMessage: (message: unknown) => void;
  setConnectionError: (error: string | null) => void;
}

export const useWSStore = create<WSStore>()(
  immer((set) => ({
    isConnected: false,
    lastMessage: null,
    connectionError: null,
    
    setConnected: (connected) => set({ isConnected: connected }),
    setLastMessage: (message) => set({ lastMessage: message }),
    setConnectionError: (error) => set({ connectionError: error }),
  }))
);

// Model Selection Store
interface ModelSelectionStore {
  // User selections
  selectedProvider: string;
  selectedModel: string;
  routingMode: string;
  
  // Available models
  localModels: ModelInfo[];
  cloudModels: Record<string, ModelInfo[]>;
  
  // Provider status
  providerStatuses: ProviderStatus[];
  
  // Active model info (resolved at runtime)
  activeProvider: string;
  activeModel: string;
  
  // Fallback tracking
  fallbackOccurred: boolean;
  fallbackReason: string | null;
  
  // Actions
  setSelectedProvider: (provider: string) => void;
  setSelectedModel: (model: string) => void;
  setRoutingMode: (mode: string) => void;
  setLocalModels: (models: ModelInfo[]) => void;
  setCloudModels: (models: Record<string, ModelInfo[]>) => void;
  setProviderStatuses: (statuses: ProviderStatus[]) => void;
  setActiveModelInfo: (provider: string, model: string) => void;
  setFallbackInfo: (occurred: boolean, reason: string | null) => void;
  reset: () => void;
}

const initialModelSelectionState = {
  selectedProvider: 'auto',
  selectedModel: '',
  routingMode: 'auto',
  localModels: [],
  cloudModels: {},
  providerStatuses: [],
  activeProvider: '',
  activeModel: '',
  fallbackOccurred: false,
  fallbackReason: null,
};

export const useModelSelectionStore = create<ModelSelectionStore>()(
  immer((set) => ({
    ...initialModelSelectionState,
    
    setSelectedProvider: (provider) => set({ selectedProvider: provider }),
    setSelectedModel: (model) => set({ selectedModel: model }),
    setRoutingMode: (mode) => set({ routingMode: mode }),
    setLocalModels: (models) => set({ localModels: models }),
    setCloudModels: (models) => set({ cloudModels: models }),
    setProviderStatuses: (statuses) => set({ providerStatuses: statuses }),
    setActiveModelInfo: (provider, model) => set({ 
      activeProvider: provider, 
      activeModel: model 
    }),
    setFallbackInfo: (occurred, reason) => set({
      fallbackOccurred: occurred,
      fallbackReason: reason,
    }),
    reset: () => set(initialModelSelectionState),
  }))
);