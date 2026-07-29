/**
 * Feature hook for on-demand training-plan generation (Phase 15, D-032).
 *
 * A mutation, not a query: unlike `useProfileAnalytics`, there is nothing to fetch on
 * mount — every plan is a real LLM generation the user asks for explicitly (D-032: no
 * caching, no auto-refresh), so an auto-firing `useQuery` here would silently spend a
 * call every time the dashboard renders. `useMutation`'s own `data` holds the most
 * recently generated plan for the component to render.
 */
import { useMutation } from '@tanstack/react-query';

import type { PersonaValue } from '@/features/reports';

import { generateTrainingPlan } from '../api/training';

export function useGenerateTrainingPlan(profileId?: string) {
  return useMutation({
    mutationFn: ({ windowSize, persona }: { windowSize: number; persona: PersonaValue }) =>
      generateTrainingPlan(windowSize, persona, profileId),
  });
}
