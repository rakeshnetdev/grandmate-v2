/**
 * Feature hooks for game ingestion.
 *
 * `useImportJob` polls while a job is still `pending`/`processing` and stops once it
 * reaches a terminal status. Phase 3's manual upload finishes synchronously — the job
 * returned from `useCreateImport` already carries a terminal status — but the polling
 * hook exists so a page can link to `/imports/:jobId` and have it behave correctly once
 * Phase 9's Lichess/Chess.com imports make jobs that genuinely take time.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';

import { gameKeys } from '@/features/games';

import { createImport, fetchImportJob, fetchImportJobs, syncFromPlatform } from '../api/imports';

export const importKeys = {
  all: ['imports'] as const,
  list: () => [...importKeys.all, 'list'] as const,
  job: (jobId: string) => [...importKeys.all, 'job', jobId] as const,
};

const TERMINAL_STATUSES = new Set(['done', 'failed']);

export function useCreateImport() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createImport,
    onSuccess: (job) => {
      queryClient.setQueryData(importKeys.job(job.id), job);
      queryClient.invalidateQueries({ queryKey: importKeys.list() });
    },
  });
}

/** Mirrors `useCreateImport` exactly — same terminal-job caching, same list
 * invalidation — the only difference is which endpoint kicks off the job. */
export function useSyncFromPlatform() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      provider,
      window,
      username,
    }: {
      provider: 'lichess' | 'chesscom';
      window?: number;
      username?: string;
    }) => syncFromPlatform(provider, window, username),
    onSuccess: (job) => {
      queryClient.setQueryData(importKeys.job(job.id), job);
      queryClient.invalidateQueries({ queryKey: importKeys.list() });
    },
  });
}

export function useImportJob(jobId: string | undefined) {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: importKeys.job(jobId ?? ''),
    queryFn: ({ signal }) => fetchImportJob(jobId as string, signal),
    enabled: Boolean(jobId),
    refetchInterval: (queryState) => {
      const status = queryState.state.data?.status;
      return status && TERMINAL_STATUSES.has(status) ? false : 1000;
    },
  });

  // A platform sync ingests games in the background, so the game list a caller is
  // looking at is stale the moment the job finishes — without this, freshly imported
  // games only appear on a manual reload, which reads as "the import did nothing".
  // Keyed on jobId + status so it fires once per job reaching a terminal state.
  const status = query.data?.status;
  useEffect(() => {
    if (status && TERMINAL_STATUSES.has(status)) {
      queryClient.invalidateQueries({ queryKey: gameKeys.all });
    }
  }, [jobId, status, queryClient]);

  return query;
}

export function useImportJobs(options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: importKeys.list(),
    queryFn: ({ signal }) => fetchImportJobs(signal),
    enabled: options.enabled ?? true,
  });
}
