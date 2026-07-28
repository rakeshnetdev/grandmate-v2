/**
 * Profile analytics API contract (Phase 8).
 *
 * Schemas mirror `backend/app/schemas/analytics.py`. One fetch function, parameterised
 * by window size — there is no separate "current" vs "history" endpoint (see the
 * backend route's docstring for why: aggregation is recomputed and re-persisted on
 * every call rather than cached).
 */
import { z } from 'zod';

import { apiClient } from '@/shared/lib/api-client';

const metricTrendSchema = z.object({
  current: z.number().nullable(),
  previous: z.number().nullable(),
  delta: z.number().nullable(),
});

const classificationRateTrendSchema = z.object({
  current: z.record(z.string(), z.number()),
  previous: z.record(z.string(), z.number()),
  delta: z.record(z.string(), z.number()).nullable(),
});

const openingFamilyPerformanceSchema = z.object({
  family: z.string(),
  games: z.number(),
  wins: z.number(),
  draws: z.number(),
  losses: z.number(),
  win_rate: z.number().nullable(),
  average_accuracy: z.number().nullable(),
});

const colorSegmentSchema = z.object({
  color: z.string(),
  games: z.number(),
  average_accuracy: z.number().nullable(),
  classification_rates: z.record(z.string(), z.number()),
  win_rate: z.number().nullable(),
});

const timeControlSegmentSchema = z.object({
  bucket: z.string(),
  games: z.number(),
  average_accuracy: z.number().nullable(),
  win_rate: z.number().nullable(),
});

const recurringWeaknessSchema = z.object({
  kind: z.enum(['motif', 'theme']),
  name: z.string(),
  games_with_finding: z.number(),
  occurrence_rate: z.number(),
});

export const profileAnalyticsSchema = z.object({
  profile_id: z.string(),
  window_size: z.number(),
  games_included: z.number(),
  sufficient_sample: z.boolean(),
  snapshot_version: z.string(),
  computed_at: z.string(),
  accuracy: metricTrendSchema,
  classification_rates: classificationRateTrendSchema,
  critical_moment_rate: metricTrendSchema,
  opening_family_performance: z.array(openingFamilyPerformanceSchema),
  color_segmentation: z.array(colorSegmentSchema),
  time_control_segmentation: z.array(timeControlSegmentSchema),
  recurring_weaknesses: z.array(recurringWeaknessSchema),
});
export type ProfileAnalytics = z.infer<typeof profileAnalyticsSchema>;
export type OpeningFamilyPerformance = z.infer<typeof openingFamilyPerformanceSchema>;
export type ColorSegment = z.infer<typeof colorSegmentSchema>;
export type TimeControlSegment = z.infer<typeof timeControlSegmentSchema>;
export type RecurringWeakness = z.infer<typeof recurringWeaknessSchema>;

export function fetchProfileAnalytics(
  windowSize: number,
  profileId?: string,
  signal?: AbortSignal,
): Promise<ProfileAnalytics> {
  const params = new URLSearchParams({ window: String(windowSize) });
  if (profileId) {
    // `undefined` means the caller's own SELF profile (Phase 8b) — the server default.
    params.set('profile_id', profileId);
  }
  return apiClient.get(
    `/api/v1/analytics/profile?${params.toString()}`,
    profileAnalyticsSchema,
    signal,
  );
}
