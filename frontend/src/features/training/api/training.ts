/**
 * Training-plan API contract (Phase 15, D-032).
 *
 * Schema mirrors `backend/app/schemas/reports.py`'s `TrainingRecommendationSummary`.
 * One fetch function, same shape as `features/reports/api/reports.ts`'s
 * `fetchGameReport` — a training plan is "a new report type" (D-032), not a new
 * request/response pattern.
 */
import { z } from 'zod';

import { apiClient } from '@/shared/lib/api-client';

import type { PersonaValue } from '@/features/reports';

// Duplicated from `features/reports/api/reports.ts`'s `personaSchema` rather than
// imported: that feature's public surface (`index.ts`) exports the `PersonaValue` type
// but not the schema value itself, and the three-value enum is stable taxonomy
// (`persona-matrix.md`), not something worth widening another feature's public API for.
const trainingPersonaSchema = z.enum(['self_learner', 'coach', 'kid']);

const trainingFindingSchema = z.object({
  fact_ids: z.array(z.string()),
  text: z.string(),
});

export const trainingRecommendationSchema = z.object({
  id: z.string(),
  profile_id: z.string(),
  persona: trainingPersonaSchema,
  window_size: z.number(),
  source: z.enum(['llm', 'fallback']),
  model: z.string().nullable(),
  snapshot_version: z.string(),
  summary: z.string(),
  findings: z.array(trainingFindingSchema),
  recommendations: z.array(z.string()),
  themes_covered: z.array(z.string()),
  grounded: z.boolean(),
  created_at: z.string(),
});
export type TrainingRecommendation = z.infer<typeof trainingRecommendationSchema>;

/**
 * Always a fresh generation — the endpoint itself has no "return the cached one" branch
 * (D-032: on-demand only, history rather than caching is what keeps a plan from
 * repeating itself). Called from a mutation, never an auto-firing query, so navigating
 * to or re-rendering the dashboard never silently spends an LLM call.
 */
export function generateTrainingPlan(
  windowSize: number,
  persona: PersonaValue,
  profileId?: string,
  signal?: AbortSignal,
): Promise<TrainingRecommendation> {
  const params = new URLSearchParams({ persona, window: String(windowSize) });
  if (profileId) {
    params.set('profile_id', profileId);
  }
  return apiClient.get(
    `/api/v1/reports/profile/training?${params.toString()}`,
    trainingRecommendationSchema,
    signal,
  );
}
