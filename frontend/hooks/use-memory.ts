import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { memoryApi } from '@/services/api';

export function useMemorySearch(query: string, sessionId?: string, limit = 10) {
  return useQuery({
    queryKey: ['memory-search', query, sessionId, limit],
    queryFn: () => memoryApi.search(query, sessionId, limit),
    enabled: query.length > 0,
  });
}

export function useSessionMemory(sessionId: string | null) {
  return useQuery({
    queryKey: ['session-memory', sessionId],
    queryFn: () => (sessionId ? memoryApi.getSessionMemory(sessionId) : null),
    enabled: !!sessionId,
  });
}

export function useMemoryStats() {
  return useQuery({
    queryKey: ['memory-stats'],
    queryFn: () => memoryApi.getStats(),
    refetchInterval: 30000,
  });
}

export function useRetrieveContext() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ query, topK = 5 }: { query: string; topK?: number }) =>
      memoryApi.retrieveContext(query, topK),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['memory-search'] });
    },
  });
}