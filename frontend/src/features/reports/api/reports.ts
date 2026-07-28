/**
 * Persona report API contract (Phase 9).
 *
 * Schema mirrors `backend/app/schemas/reports.py`.
 */
import { z } from 'zod';

import { apiClient } from '@/shared/lib/api-client';

export const personaSchema = z.enum(['self_learner', 'coach', 'kid']);
export type PersonaValue = z.infer<typeof personaSchema>;

const reportFindingSchema = z.object({
  fact_ids: z.array(z.string()),
  text: z.string(),
});

export const gameReportSchema = z.object({
  id: z.string(),
  game_id: z.string(),
  persona: personaSchema,
  source: z.enum(['llm', 'fallback']),
  model: z.string().nullable(),
  analysis_version: z.string(),
  summary: z.string(),
  findings: z.array(reportFindingSchema),
  recommendations: z.array(z.string()),
  grounded: z.boolean(),
  created_at: z.string(),
});
export type GameReport = z.infer<typeof gameReportSchema>;
export type ReportFinding = z.infer<typeof reportFindingSchema>;

export function fetchGameReport(
  gameId: string,
  persona: PersonaValue,
  profileId?: string,
  signal?: AbortSignal,
): Promise<GameReport> {
  const params = new URLSearchParams({ persona });
  if (profileId) {
    params.set('profile_id', profileId);
  }
  return apiClient.get(
    `/api/v1/reports/games/${gameId}?${params.toString()}`,
    gameReportSchema,
    signal,
  );
}
