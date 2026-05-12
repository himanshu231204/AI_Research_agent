import { describe, it, expect, beforeEach } from 'vitest';
import {
  useUIStore,
  useChatStore,
  useResearchStore,
  useAgentsStore,
  useWorkflowStore,
  useTimelineStore,
  useSessionsStore,
  useWSStore,
} from '@/stores';

describe('UI Store', () => {
  beforeEach(() => {
    useUIStore.getState().setTheme('dark');
    useUIStore.getState().setSidebarOpen(true);
  });

  it('sets theme correctly', () => {
    useUIStore.getState().setTheme('light');
    expect(useUIStore.getState().theme).toBe('light');
  });

  it('toggles sidebar', () => {
    const initialState = useUIStore.getState().sidebarOpen;
    useUIStore.getState().toggleSidebar();
    expect(useUIStore.getState().sidebarOpen).toBe(!initialState);
  });

  it('sets active panel', () => {
    useUIStore.getState().setActivePanel('workflow');
    expect(useUIStore.getState().activePanel).toBe('workflow');
  });
});

describe('Chat Store', () => {
  beforeEach(() => {
    useChatStore.getState().clearMessages();
  });

  it('adds messages', () => {
    useChatStore.getState().addMessage({
      id: '1',
      role: 'user',
      content: 'Hello',
      timestamp: new Date().toISOString(),
    });
    expect(useChatStore.getState().messages.length).toBe(1);
  });

  it('updates messages', () => {
    useChatStore.getState().addMessage({
      id: '1',
      role: 'user',
      content: 'Hello',
      timestamp: new Date().toISOString(),
    });
    useChatStore.getState().updateMessage('1', { content: 'Updated' });
    expect(useChatStore.getState().messages[0].content).toBe('Updated');
  });

  it('clears messages', () => {
    useChatStore.getState().addMessage({
      id: '1',
      role: 'user',
      content: 'Hello',
      timestamp: new Date().toISOString(),
    });
    useChatStore.getState().clearMessages();
    expect(useChatStore.getState().messages.length).toBe(0);
  });
});

describe('Research Store', () => {
  beforeEach(() => {
    useResearchStore.getState().reset();
  });

  it('sets session ID', () => {
    useResearchStore.getState().setSessionId('session-123');
    expect(useResearchStore.getState().currentSessionId).toBe('session-123');
  });

  it('sets status', () => {
    useResearchStore.getState().setStatus('researching');
    expect(useResearchStore.getState().status).toBe('researching');
  });

  it('sets progress', () => {
    useResearchStore.getState().setProgress(0.5);
    expect(useResearchStore.getState().progress).toBe(0.5);
  });

  it('adds findings', () => {
    useResearchStore.getState().addFinding({
      id: '1',
      source: 'test',
      content: 'Test finding',
    });
    expect(useResearchStore.getState().findings.length).toBe(1);
  });

  it('resets state', () => {
    useResearchStore.getState().setSessionId('session-123');
    useResearchStore.getState().setStatus('completed');
    useResearchStore.getState().reset();
    expect(useResearchStore.getState().currentSessionId).toBeNull();
    expect(useResearchStore.getState().status).toBe('pending');
  });
});

describe('Agents Store', () => {
  it('sets agents', () => {
    const agents = [
      { id: '1', name: 'planner' as const, status: 'idle' as const },
    ];
    useAgentsStore.getState().setAgents(agents);
    expect(useAgentsStore.getState().agents.length).toBe(1);
  });

  it('updates agent', () => {
    useAgentsStore.getState().setAgents([
      { id: '1', name: 'planner' as const, status: 'idle' as const },
    ]);
    useAgentsStore.getState().updateAgent('1', { status: 'running' });
    expect(useAgentsStore.getState().agents[0].status).toBe('running');
  });
});

describe('Timeline Store', () => {
  beforeEach(() => {
    useTimelineStore.getState().clearEvents();
  });

  it('adds events', () => {
    useTimelineStore.getState().addEvent({
      id: '1',
      type: 'search',
      message: 'Test event',
      timestamp: new Date().toISOString(),
    });
    expect(useTimelineStore.getState().events.length).toBe(1);
  });

  it('clears events', () => {
    useTimelineStore.getState().addEvent({
      id: '1',
      type: 'search',
      message: 'Test event',
      timestamp: new Date().toISOString(),
    });
    useTimelineStore.getState().clearEvents();
    expect(useTimelineStore.getState().events.length).toBe(0);
  });
});

describe('WebSocket Store', () => {
  it('sets connected state', () => {
    useWSStore.getState().setConnected(true);
    expect(useWSStore.getState().isConnected).toBe(true);
  });

  it('sets connection error', () => {
    useWSStore.getState().setConnectionError('Connection failed');
    expect(useWSStore.getState().connectionError).toBe('Connection failed');
  });

  it('sets last message', () => {
    useWSStore.getState().setLastMessage({ type: 'test', payload: {} });
    expect(useWSStore.getState().lastMessage).toEqual({ type: 'test', payload: {} });
  });
});