/**
 * Frontend tests for model selection system.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ModelSelector } from '../../features/chat/model-selector';

// Mock the API
vi.mock('@/services/api', () => ({
  modelsApi: {
    getAllModels: vi.fn().mockResolvedValue({
      local: [
        { name: 'qwen3', provider: 'ollama', model_type: 'chat', is_local: true, available: true, health_status: 'healthy', latency_ms: 50, display_name: 'Qwen3', icon: '🖥️' },
        { name: 'llama3', provider: 'ollama', model_type: 'chat', is_local: true, available: true, health_status: 'healthy', latency_ms: 60, display_name: 'Llama3', icon: '🖥️' },
      ],
      cloud: {
        openai: [
          { name: 'gpt-4o', provider: 'openai', model_type: 'chat', is_local: false, available: true, health_status: 'healthy', latency_ms: 100, display_name: 'GPT-4o', icon: '☁️' },
        ],
      },
      timestamp: '2024-01-01T00:00:00Z',
    }),
    getProviderStatus: vi.fn().mockResolvedValue({
      providers: [
        { name: 'ollama', provider_type: 'local', status: 'healthy', available: true, models: ['qwen3', 'llama3'], latency_ms: 50, status_icon: '🟢' },
        { name: 'openai', provider_type: 'cloud', status: 'healthy', available: true, models: ['gpt-4o'], latency_ms: 100, status_icon: '🟢' },
      ],
    }),
    selectModel: vi.fn().mockResolvedValue({ success: true }),
    refreshLocalModels: vi.fn().mockResolvedValue({ success: true, models: ['qwen3'], count: 1 }),
  },
}));

// Mock the stores
vi.mock('@/stores', () => ({
  useChatStore: {
    getState: () => ({ currentSessionId: 'test-session-123' }),
  },
  useModelSelectionStore: {
    getState: () => ({
      selectedProvider: 'auto',
      selectedModel: '',
      routingMode: 'auto',
      localModels: [],
      cloudModels: {},
      providerStatuses: [],
      activeProvider: '',
      activeModel: '',
      setSelectedProvider: vi.fn(),
      setSelectedModel: vi.fn(),
      setRoutingMode: vi.fn(),
      setLocalModels: vi.fn(),
      setCloudModels: vi.fn(),
      setProviderStatuses: vi.fn(),
      setActiveModelInfo: vi.fn(),
    }),
  },
}));

describe('ModelSelector', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the model selector button', () => {
    render(<ModelSelector />);
    
    // Should show "Auto" by default
    expect(screen.getByText('Auto')).toBeDefined();
  });

  it('opens dropdown when clicked', async () => {
    render(<ModelSelector />);
    
    const button = screen.getByText('Auto');
    fireEvent.click(button);
    
    // Should show provider options
    await waitFor(() => {
      expect(screen.getByText('Provider')).toBeDefined();
    });
  });

  it('shows all provider options', async () => {
    render(<ModelSelector />);
    
    const button = screen.getByText('Auto');
    fireEvent.click(button);
    
    await waitFor(() => {
      expect(screen.getByText('Ollama')).toBeDefined();
      expect(screen.getByText('OpenAI')).toBeDefined();
      expect(screen.getByText('Anthropic')).toBeDefined();
      expect(screen.getByText('Google')).toBeDefined();
      expect(screen.getByText('Groq')).toBeDefined();
    });
  });

  it('shows routing mode options', async () => {
    render(<ModelSelector />);
    
    const button = screen.getByText('Auto');
    fireEvent.click(button);
    
    await waitFor(() => {
      expect(screen.getByText('Routing Mode')).toBeDefined();
      expect(screen.getByText('Auto Routing')).toBeDefined();
      expect(screen.getByText('Local Only')).toBeDefined();
      expect(screen.getByText('Cloud Only')).toBeDefined();
      expect(screen.getByText('Hybrid')).toBeDefined();
    });
  });

  it('allows selecting a provider', async () => {
    render(<ModelSelector />);
    
    const button = screen.getByText('Auto');
    fireEvent.click(button);
    
    // Click on Ollama
    await waitFor(() => {
      const ollamaButton = screen.getByText('Ollama');
      fireEvent.click(ollamaButton);
    });
    
    // Should show local models
    await waitFor(() => {
      expect(screen.getByText('Qwen3')).toBeDefined();
      expect(screen.getByText('Llama3')).toBeDefined();
    });
  });

  it('shows provider status indicators', async () => {
    render(<ModelSelector />);
    
    const button = screen.getByText('Auto');
    fireEvent.click(button);
    
    await waitFor(() => {
      // Should show status icons
      expect(screen.getByText('🟢')).toBeDefined();
    });
  });
});

describe('Model Selection Store', () => {
  it('should have correct initial state', async () => {
    const { useModelSelectionStore } = await import('@/stores');
    
    const state = useModelSelectionStore.getState();
    
    expect(state.selectedProvider).toBe('auto');
    expect(state.selectedModel).toBe('');
    expect(state.routingMode).toBe('auto');
    expect(state.localModels).toEqual([]);
    expect(state.cloudModels).toEqual({});
  });
});

describe('API Integration', () => {
  it('should fetch all models', async () => {
    const { modelsApi } = await import('@/services/api');
    
    const result = await modelsApi.getAllModels();
    
    expect(result.local).toBeDefined();
    expect(result.cloud).toBeDefined();
    expect(result.timestamp).toBeDefined();
  });

  it('should fetch provider status', async () => {
    const { modelsApi } = await import('@/services/api');
    
    const result = await modelsApi.getProviderStatus();
    
    expect(result.providers).toBeDefined();
    expect(result.providers.length).toBeGreaterThan(0);
  });

  it('should select model', async () => {
    const { modelsApi } = await import('@/services/api');
    
    const result = await modelsApi.selectModel('test-session', 'ollama', 'qwen3', 'auto');
    
    expect(result.success).toBe(true);
  });
});