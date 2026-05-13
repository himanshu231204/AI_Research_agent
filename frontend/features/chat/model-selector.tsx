'use client';

import { useState, useEffect, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useChatStore, useModelSelectionStore } from '@/stores';
import { modelsApi } from '@/services/api';
import { cn } from '@/lib/utils';
import {
  ChevronDown,
  RefreshCw,
  Check,
  AlertCircle,
  Loader2,
  Monitor,
  Cloud,
  Zap,
} from 'lucide-react';

// Provider configuration
const PROVIDERS = [
  { id: 'auto', name: 'Auto', icon: Zap, description: 'System chooses best model' },
  { id: 'ollama', name: 'Ollama', icon: Monitor, description: 'Local models' },
  { id: 'openai', name: 'OpenAI', icon: Cloud, description: 'GPT models' },
  { id: 'anthropic', name: 'Anthropic', icon: Cloud, description: 'Claude models' },
  { id: 'google', name: 'Google', icon: Cloud, description: 'Gemini models' },
  { id: 'groq', name: 'Groq', icon: Cloud, description: 'Fast inference' },
] as const;

// Routing modes
const ROUTING_MODES = [
  { id: 'auto', name: 'Auto Routing', description: 'System chooses automatically' },
  { id: 'local_only', name: 'Local Only', description: 'Use only Ollama models' },
  { id: 'cloud_only', name: 'Cloud Only', description: 'Use only cloud providers' },
  { id: 'hybrid', name: 'Hybrid', description: 'Prefer local, fallback to cloud' },
] as const;

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

export function ModelSelector() {
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  
  // State from store
  const {
    selectedProvider,
    selectedModel,
    routingMode,
    localModels,
    cloudModels,
    providerStatuses,
    activeProvider,
    activeModel,
    setSelectedProvider,
    setSelectedModel,
    setRoutingMode,
    setLocalModels,
    setCloudModels,
    setProviderStatuses,
    setActiveModelInfo,
  } = useModelSelectionStore();

  const { currentSessionId } = useChatStore();

  // Fetch available models
  const fetchModels = useCallback(async () => {
    setIsLoading(true);
    try {
      const [allModels, providerStatus] = await Promise.all([
        modelsApi.getAllModels(),
        modelsApi.getProviderStatus(),
      ]);

      setLocalModels(allModels.local);
      setCloudModels(allModels.cloud);
      setProviderStatuses(providerStatus.providers);

      // Set default model if none selected
      if (allModels.local.length > 0 && !selectedModel) {
        setSelectedModel(allModels.local[0].name);
      }
    } catch (error) {
      console.error('Failed to fetch models:', error);
    } finally {
      setIsLoading(false);
    }
  }, [setLocalModels, setCloudModels, setProviderStatuses, setSelectedModel, selectedModel]);

  // Initial fetch
  useEffect(() => {
    fetchModels();
    
    // Refresh every 30 seconds
    const interval = setInterval(fetchModels, 30000);
    return () => clearInterval(interval);
  }, [fetchModels]);

  // Handle provider change
  const handleProviderChange = async (provider: string) => {
    setSelectedProvider(provider);
    
    // Reset model when provider changes
    setSelectedModel('');
    
    // If provider is selected (not auto), update backend
    if (provider !== 'auto' && currentSessionId) {
      try {
        await modelsApi.selectModel(currentSessionId, provider, '', routingMode);
      } catch (error) {
        console.error('Failed to update provider selection:', error);
      }
    }
  };

  // Handle model change
  const handleModelChange = async (model: string) => {
    setSelectedModel(model);
    
    if (currentSessionId && selectedProvider !== 'auto') {
      try {
        await modelsApi.selectModel(currentSessionId, selectedProvider, model, routingMode);
      } catch (error) {
        console.error('Failed to update model selection:', error);
      }
    }
  };

  // Handle routing mode change
  const handleRoutingModeChange = async (mode: string) => {
    setRoutingMode(mode);
    
    if (currentSessionId) {
      try {
        await modelsApi.selectModel(currentSessionId, selectedProvider, selectedModel, mode);
      } catch (error) {
        console.error('Failed to update routing mode:', error);
      }
    }
  };

  // Handle refresh local models
  const handleRefreshLocal = async () => {
    setIsRefreshing(true);
    try {
      const result = await modelsApi.refreshLocalModels();
      if (result.success) {
        await fetchModels();
      }
    } catch (error) {
      console.error('Failed to refresh local models:', error);
    } finally {
      setIsRefreshing(false);
    }
  };

  // Get current provider info
  const currentProviderInfo = PROVIDERS.find(p => p.id === selectedProvider);
  const currentProviderStatus = providerStatuses.find(p => p.name === selectedProvider);

  // Get models for selected provider
  const getAvailableModels = (): ModelInfo[] => {
    if (selectedProvider === 'auto' || selectedProvider === 'ollama') {
      return localModels;
    }
    return cloudModels[selectedProvider] || [];
  };

  const availableModels = getAvailableModels();

  return (
    <div className="relative">
      {/* Model Selector Button */}
      <Button
        variant="outline"
        size="sm"
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 h-8 px-2"
      >
        <div className="flex items-center gap-1.5">
          {currentProviderInfo?.icon && (
            <currentProviderInfo.icon className="h-4 w-4" />
          )}
          <span className="text-sm font-medium">
            {selectedProvider === 'auto' 
              ? 'Auto' 
              : selectedProvider === 'ollama'
                ? selectedModel || 'Local'
                : selectedModel || currentProviderInfo?.name || 'Select'}
          </span>
        </div>
        
        {/* Provider status indicator */}
        {currentProviderStatus && (
          <span className="text-xs">{currentProviderStatus.status_icon}</span>
        )}
        
        <ChevronDown className={cn(
          "h-4 w-4 transition-transform",
          isOpen && "rotate-180"
        )} />
      </Button>

      {/* Dropdown Panel */}
      {isOpen && (
        <div className="absolute top-full left-0 mt-2 w-80 bg-background border rounded-lg shadow-lg z-50">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b">
            <h3 className="font-semibold text-sm">Model Selection</h3>
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              onClick={handleRefreshLocal}
              disabled={isRefreshing}
            >
              <RefreshCw className={cn("h-4 w-4", isRefreshing && "animate-spin")} />
            </Button>
          </div>

          {/* Provider Selection */}
          <div className="p-3 border-b">
            <label className="text-xs text-muted-foreground mb-2 block">Provider</label>
            <div className="grid grid-cols-3 gap-2">
              {PROVIDERS.map((provider) => {
                const status = providerStatuses.find(p => p.name === provider.id);
                const isAvailable = provider.id === 'auto' || status?.available;
                
                return (
                  <button
                    key={provider.id}
                    onClick={() => handleProviderChange(provider.id)}
                    disabled={!isAvailable && provider.id !== 'auto'}
                    className={cn(
                      "flex flex-col items-center gap-1 p-2 rounded-md border transition-colors",
                      selectedProvider === provider.id
                        ? "bg-primary/10 border-primary"
                        : "hover:bg-muted/50",
                      !isAvailable && provider.id !== 'auto' && "opacity-50 cursor-not-allowed"
                    )}
                  >
                    <provider.icon className="h-4 w-4" />
                    <span className="text-xs">{provider.name}</span>
                    {status && provider.id !== 'auto' && (
                      <span className="text-[10px]">{status.status_icon}</span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Model Selection */}
          {selectedProvider !== 'auto' && (
            <div className="p-3 border-b max-h-48 overflow-y-auto">
              <label className="text-xs text-muted-foreground mb-2 block">Model</label>
              <div className="space-y-1">
                {availableModels.length === 0 ? (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground py-2">
                    <AlertCircle className="h-4 w-4" />
                    <span>No models available</span>
                  </div>
                ) : (
                  availableModels.map((model) => (
                    <button
                      key={model.name}
                      onClick={() => handleModelChange(model.name)}
                      className={cn(
                        "w-full flex items-center justify-between px-3 py-2 rounded-md text-sm transition-colors",
                        selectedModel === model.name
                          ? "bg-primary/10"
                          : "hover:bg-muted/50"
                      )}
                    >
                      <div className="flex items-center gap-2">
                        <span>{model.icon}</span>
                        <span>{model.display_name}</span>
                      </div>
                      {selectedModel === model.name && (
                        <Check className="h-4 w-4 text-primary" />
                      )}
                    </button>
                  ))
                )}
              </div>
            </div>
          )}

          {/* Routing Mode Selection */}
          <div className="p-3">
            <label className="text-xs text-muted-foreground mb-2 block">Routing Mode</label>
            <div className="space-y-1">
              {ROUTING_MODES.map((mode) => (
                <button
                  key={mode.id}
                  onClick={() => handleRoutingModeChange(mode.id)}
                  className={cn(
                    "w-full flex items-center justify-between px-3 py-2 rounded-md text-sm transition-colors",
                    routingMode === mode.id
                      ? "bg-primary/10"
                      : "hover:bg-muted/50"
                  )}
                >
                  <div className="flex flex-col items-start">
                    <span>{mode.name}</span>
                    <span className="text-xs text-muted-foreground">{mode.description}</span>
                  </div>
                  {routingMode === mode.id && (
                    <Check className="h-4 w-4 text-primary" />
                  )}
                </button>
              ))}
            </div>
          </div>

          {/* Active Model Info */}
          {(activeProvider || activeModel) && (
            <div className="px-4 py-3 bg-muted/30 border-t">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <span>Active:</span>
                <Badge variant="outline" className="text-xs">
                  {activeProvider}/{activeModel}
                </Badge>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default ModelSelector;