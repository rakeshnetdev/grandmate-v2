/**
 * Import API contract.
 *
 * Schemas mirror `backend/app/schemas/imports.py`. A submission may carry pasted text,
 * one file, or several files together — the backend treats a single-game PGN as the N=1
 * case of the same batch path, so there is one `createImport` call, not a separate one
 * for "single" vs "batch".
 */
import { z } from 'zod';

import { apiClient } from '@/shared/lib/api-client';

const rejectedGameSchema = z.object({
  source: z.string(),
  index: z.number(),
  reason: z.string(),
  detail: z.string(),
});

const jobProgressSchema = z.object({
  total: z.number().default(0),
  imported: z.number().default(0),
  duplicates: z.number().default(0),
  rejected: z.array(rejectedGameSchema).default([]),
});

export const jobSummarySchema = z.object({
  id: z.string(),
  kind: z.string(),
  status: z.enum(['pending', 'processing', 'done', 'failed']),
  progress: jobProgressSchema,
  error: z.record(z.string(), z.unknown()).nullable(),
  created_at: z.string(),
  completed_at: z.string().nullable(),
});
export type JobSummary = z.infer<typeof jobSummarySchema>;
export type RejectedGame = z.infer<typeof rejectedGameSchema>;

const jobListSchema = z.array(jobSummarySchema);

/** Submit pasted PGN text, uploaded files, or both together as one import job. */
export function createImport(input: { pgnText?: string; files?: File[] }): Promise<JobSummary> {
  const form = new FormData();
  if (input.pgnText && input.pgnText.trim()) {
    form.append('pgn_text', input.pgnText);
  }
  for (const file of input.files ?? []) {
    form.append('files', file);
  }
  return apiClient.post('/api/v1/imports', jobSummarySchema, form);
}

export function fetchImportJob(jobId: string, signal?: AbortSignal): Promise<JobSummary> {
  return apiClient.get(`/api/v1/imports/${jobId}`, jobSummarySchema, signal);
}

export function fetchImportJobs(signal?: AbortSignal): Promise<JobSummary[]> {
  return apiClient.get('/api/v1/imports', jobListSchema, signal);
}

/**
 * Sync recent games from Lichess/Chess.com (Phase 14, D-030/D-031).
 *
 * Returns immediately with a `pending` job — the platform fetch and ingestion run in
 * the background server-side, so callers should hand the returned job id to
 * `ImportJobStatus`/`useImportJob`, the same polling path a manual upload's job uses.
 *
 * `username` omitted syncs the caller's own linked account. Supplying one imports a
 * player being studied; the backend routes those games to the study profile on its own
 * (see `PlatformSyncRequest`), so there is no target-profile argument here.
 */
export function syncFromPlatform(
  provider: 'lichess' | 'chesscom',
  window?: number,
  username?: string,
): Promise<JobSummary> {
  return apiClient.post(`/api/v1/imports/${provider}/sync`, jobSummarySchema, {
    window,
    username,
  });
}
