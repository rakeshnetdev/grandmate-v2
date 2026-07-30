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
  // "strength"/"mistake" (Phase 16a, D-035 addendum) group the per-game findings report
  // under "What Went Well" vs "Mistakes & Blunders"; "opening"/"middlegame"/"endgame"/
  // "lesson" (Phase 16b) do the same for the full game-story report. null/absent for
  // coach and kid, which use neither format.
  kind: z.enum(['strength', 'mistake', 'opening', 'middlegame', 'endgame', 'lesson']).nullish(),
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

/** The full opening/middlegame/endgame game-story report (Phase 16b) — self-learner
 * only, no `persona` param (unlike `fetchGameReport`). */
export function fetchGameStory(
  gameId: string,
  profileId?: string,
  signal?: AbortSignal,
): Promise<GameReport> {
  const params = new URLSearchParams();
  if (profileId) {
    params.set('profile_id', profileId);
  }
  const query = params.toString();
  return apiClient.get(
    `/api/v1/reports/games/${gameId}/story${query ? `?${query}` : ''}`,
    gameReportSchema,
    signal,
  );
}
