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

import { createImport, fetchImportJob, fetchImportJobs } from '../api/imports';

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

export function useImportJob(jobId: string | undefined) {
  return useQuery({
    queryKey: importKeys.job(jobId ?? ''),
    queryFn: ({ signal }) => fetchImportJob(jobId as string, signal),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && TERMINAL_STATUSES.has(status) ? false : 1000;
    },
  });
}

export function useImportJobs(options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: importKeys.list(),
    queryFn: ({ signal }) => fetchImportJobs(signal),
    enabled: options.enabled ?? true,
  });
}
