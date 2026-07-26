/**
 * Developer insight hooks.
 *
 * Queries are **disabled until the panel is opened**. That is the point of the separate
 * endpoint: a closed panel costs nothing, so tracing adds no request-path overhead for
 * developers who are not looking at it.
 */
import { useQuery } from '@tanstack/react-query';

import { fetchTrace, fetchTraces } from '../api/traces';

export const devInsightKeys = {
  all: ['devinsight'] as const,
  traces: () => [...devInsightKeys.all, 'traces'] as const,
  trace: (id: string) => [...devInsightKeys.all, 'trace', id] as const,
};

export function useTraces(enabled: boolean) {
  return useQuery({
    queryKey: devInsightKeys.traces(),
    queryFn: ({ signal }) => fetchTraces(signal),
    enabled,
    // Traces accumulate as the developer clicks around, so a short stale time keeps the
    // list current without polling.
    staleTime: 2_000,
    // A 404 means tracing is disabled on this backend. Retrying will not change that.
    retry: false,
  });
}

export function useTrace(traceId: string | null) {
  return useQuery({
    queryKey: devInsightKeys.trace(traceId ?? ''),
    queryFn: ({ signal }) => fetchTrace(traceId as string, signal),
    enabled: traceId !== null,
    // A completed trace is immutable, so it never needs refetching.
    staleTime: Infinity,
    retry: false,
  });
}
