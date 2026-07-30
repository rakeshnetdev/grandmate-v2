/**
 * Feature hooks for the profile training analysis (Phase 15, D-032).
 *
 * A query *and* a mutation, since the backend is get-or-generate (like game reports):
 * a stored plan is returned while the analytics snapshot it was built from is still
 * current, so loading on mount costs nothing when one already exists — it only spends
 * an LLM call the first time, or after the window's data moves on. The mutation is the
 * explicit "Regenerate" action, which always spends one; its result seeds the query so
 * the panel shows it immediately.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type { PersonaValue } from '@/features/reports';

import { fetchTrainingPlan } from '../api/training';

const SELF_KEY = 'self';

export const trainingKeys = {
  all: ['training'] as const,
  plan: (profileId: string | undefined, windowSize: number, persona: PersonaValue) =>
    [...trainingKeys.all, profileId ?? SELF_KEY, windowSize, persona] as const,
};

export function useTrainingPlan(
  windowSize: number,
  persona: PersonaValue,
  profileId?: string,
  options: { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: trainingKeys.plan(profileId, windowSize, persona),
    queryFn: ({ signal }) => fetchTrainingPlan(windowSize, persona, profileId, {}, signal),
    enabled: options.enabled ?? true,
    // The server decides staleness (by analytics snapshot version); refetching on focus
    // would just re-ask the same question.
    staleTime: Infinity,
    retry: false,
  });
}

export function useGenerateTrainingPlan(profileId?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ windowSize, persona }: { windowSize: number; persona: PersonaValue }) =>
      fetchTrainingPlan(windowSize, persona, profileId, { regenerate: true }),
    onSuccess: (plan, { windowSize, persona }) => {
      queryClient.setQueryData(trainingKeys.plan(profileId, windowSize, persona), plan);
    },
  });
}
