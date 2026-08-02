/**
 * Pattern feedback API contract (Phase 19, D-037).
 *
 * Schema mirrors `PatternFeedbackSummary` in `backend/app/schemas/reports.py`.
 *
 * The response deliberately carries both the deterministic comparison and the generated
 * prose. The tab renders the numbers itself and uses the report only for explanation, so
 * a reader can always see the sample size a claim rests on.
 */
import { z } from 'zod';

import { gameReportSchema } from '@/features/reports';
import { apiClient } from '@/shared/lib/api-client';

/** How this game compares to the player's recent form, in plain terms. */
export const bandSchema = z.enum(['well_above', 'above', 'in_line', 'below', 'well_below']);
export type Band = z.infer<typeof bandSchema>;

const repeatedWeaknessSchema = z.object({
  kind: z.enum(['motif', 'theme']),
  name: z.string(),
  baseline_games_with_finding: z.number(),
  baseline_games: z.number(),
  occurrence_rate: z.number(),
  move_numbers: z.array(z.number()),
});

const improvedWeaknessSchema = z.object({
  kind: z.enum(['motif', 'theme']),
  name: z.string(),
  baseline_games_with_finding: z.number(),
  baseline_games: z.number(),
  occurrence_rate: z.number(),
  clear_streak: z.number(),
  // False means "absent from this one game", not "fixed". The UI words the two
  // differently; see `ImprovedList`.
  sustained: z.boolean(),
});

const metricComparisonSchema = z.object({
  name: z.enum(['accuracy', 'blunder_rate', 'critical_moments']),
  value: z.number(),
  baseline_mean: z.number(),
  z_score: z.number().nullable(),
  band: bandSchema,
});

export const patternFeedbackSchema = z.object({
  game_id: z.string(),
  baseline_games: z.number(),
  sufficient_baseline: z.boolean(),
  attributable: z.boolean(),
  outcome: z.enum(['win', 'draw', 'loss', 'unknown']),
  overall_band: bandSchema,
  repeated: z.array(repeatedWeaknessSchema),
  improved: z.array(improvedWeaknessSchema),
  metrics: z.array(metricComparisonSchema),
  // Null when the baseline is too thin to support any claim — a normal state for a new
  // player, not an error.
  report: gameReportSchema.nullable(),
});

export type PatternFeedback = z.infer<typeof patternFeedbackSchema>;
export type RepeatedWeakness = z.infer<typeof repeatedWeaknessSchema>;
export type ImprovedWeakness = z.infer<typeof improvedWeaknessSchema>;
export type MetricComparison = z.infer<typeof metricComparisonSchema>;

/** `regenerate` forces a fresh generation (the explicit "Regenerate" action), matching
 * the training plan's existing contract. */
export function fetchPatternFeedback(
  gameId: string,
  profileId?: string,
  options: { regenerate?: boolean } = {},
  signal?: AbortSignal,
): Promise<PatternFeedback> {
  const params = new URLSearchParams();
  if (profileId) {
    params.set('profile_id', profileId);
  }
  if (options.regenerate) {
    params.set('regenerate', 'true');
  }
  const query = params.toString();
  return apiClient.get(
    `/api/v1/reports/games/${gameId}/pattern-feedback${query ? `?${query}` : ''}`,
    patternFeedbackSchema,
    signal,
  );
}
