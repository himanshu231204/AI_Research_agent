import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { modelsApi } from '@/services/api';

export function useModelStatus() {
  return useQuery({
    queryKey: ['model-status'],
    queryFn: () => modelsApi.getStatus(),
    refetchInterval: 10000,
  });
}

export function useModelProviders() {
  return useQuery({
    queryKey: ['model-providers'],
    queryFn: () => modelsApi.getProviders(),
    refetchInterval: 30000,
  });
}

export function useModelTelemetry() {
  return useQuery({
    queryKey: ['model-telemetry'],
    queryFn: () => modelsApi.getTelemetry(),
    refetchInterval: 30000,
  });
}

export function useCostTelemetry(sessionId = 'default') {
  return useQuery({
    queryKey: ['cost-telemetry', sessionId],
    queryFn: () => modelsApi.getCostTelemetry(sessionId),
    refetchInterval: 30000,
  });
}

export function useTestModel() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      provider,
      model,
      prompt = 'Hello, world!',
      temperature = 0.7,
    }: {
      provider: string;
      model: string;
      prompt?: string;
      temperature?: number;
    }) => modelsApi.testModel(provider, model, prompt, temperature),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['model-status'] });
    },
  });
}

export function useRoutingStats() {
  return useQuery({
    queryKey: ['routing-stats'],
    queryFn: () => modelsApi.getRoutingStats(),
    refetchInterval: 30000,
  });
}