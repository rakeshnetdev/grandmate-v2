/**
 * Feature hooks for the long-term memory audit surface (Phase 11, ADR-0005).
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { deleteMemory, listMemories } from '../api/memory';

const SELF_KEY = 'self';

export const memoryKeys = {
  all: ['memory'] as const,
  list: (profileId: string | undefined) => [...memoryKeys.all, profileId ?? SELF_KEY] as const,
};

export function useMemories(profileId?: string) {
  return useQuery({
    queryKey: memoryKeys.list(profileId),
    queryFn: ({ signal }) => listMemories(profileId, signal),
  });
}

export function useDeleteMemory(profileId?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (memoryId: string) => deleteMemory(memoryId, profileId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: memoryKeys.list(profileId) });
    },
  });
}
