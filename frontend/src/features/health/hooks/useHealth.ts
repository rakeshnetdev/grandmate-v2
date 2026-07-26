/**
 * Feature hooks for backend health.
 *
 * Components consume these rather than calling the API module directly, so caching,
 * retry, and loading state are handled once by TanStack Query instead of re-implemented
 * per component.
 */
import { useQuery } from '@tanstack/react-query';

import { fetchHealth, fetchReadiness } from '../api/health';

/** Query keys are centralised so invalidation cannot drift from subscription. */
export const healthKeys = {
  all: ['health'] as const,
  liveness: () => [...healthKeys.all, 'liveness'] as const,
  readiness: () => [...healthKeys.all, 'readiness'] as const,
};

export function useHealth() {
  return useQuery({
    queryKey: healthKeys.liveness(),
    queryFn: ({ signal }) => fetchHealth(signal),
  });
}

export function useReadiness() {
  return useQuery({
    queryKey: healthKeys.readiness(),
    queryFn: ({ signal }) => fetchReadiness(signal),
    // Readiness reflects configuration that changes on deploy, not per interaction.
    staleTime: 30_000,
  });
}
