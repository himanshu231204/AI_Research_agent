import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { researchApi } from '@/services/api';
import type { ResearchRequest, ResearchStatusResponse } from '@/types';

export function useResearch() {
  const queryClient = useQueryClient();

  const createMutation = useMutation({
    mutationFn: (request: ResearchRequest) => researchApi.create(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['research-sessions'] });
    },
  });

  const listQuery = useQuery({
    queryKey: ['research-sessions'],
    queryFn: () => researchApi.list(10, 0),
    refetchInterval: 5000,
  });

  return {
    create: createMutation.mutate,
    createAsync: createMutation.mutateAsync,
    isCreating: createMutation.isPending,
    sessions: listQuery.data?.sessions || [],
    isLoadingSessions: listQuery.isLoading,
    refetchSessions: listQuery.refetch,
  };
}

export function useResearchStatus(sessionId: string | null) {
  return useQuery({
    queryKey: ['research-status', sessionId],
    queryFn: () => (sessionId ? researchApi.getStatus(sessionId) : null),
    enabled: !!sessionId,
    refetchInterval: 2000,
  });
}

export function useCancelResearch() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (sessionId: string) => researchApi.cancel(sessionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['research-sessions'] });
    },
  });
}