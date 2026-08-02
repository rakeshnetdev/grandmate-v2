/**
 * Feature hook for pattern feedback (Phase 19, D-037).
 *
 * Same waiting behaviour as the report hooks: generation is synchronous within the
 * request, but the engine analysis it is built from is not, so the query polls while —
 * and only while — the server says the game is still being analyzed.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { isAnalysisPending } from '@/features/reports';

import { fetchPatternFeedback } from '../api/patternFeedback';

/** Matches the reports feature's cadence — a game is roughly 7s of engine work. */
const ANALYSIS_POLL_MS = 4000;

const SELF_KEY = 'self';

export const patternFeedbackKeys = {
  all: ['pattern-feedback'] as const,
  game: (gameId: string, profileId: string | undefined) =>
    [...patternFeedbackKeys.all, profileId ?? SELF_KEY, gameId] as const,
};

export function usePatternFeedback(gameId: string | undefined, profileId?: string) {
  return useQuery({
    queryKey: patternFeedbackKeys.game(gameId ?? '', profileId),
    queryFn: ({ signal }) => fetchPatternFeedback(gameId as string, profileId, {}, signal),
    enabled: Boolean(gameId),
    // Cached server-side against the game's analysis version *and* its baseline size, so
    // a refetch on window focus would re-derive an identical answer.
    staleTime: Infinity,
    retry: (_failureCount: number, error: unknown) => isAnalysisPending(error),
    retryDelay: ANALYSIS_POLL_MS,
  });
}

/**
 * The explicit "Regenerate" action.
 *
 * A mutation rather than a query refetch, because it is not the same request: it spends
 * an LLM call every time by design, so it has to be something the user asks for once,
 * never something a refocus or a remount can trigger. The result is written straight into
 * the query's cache so the panel re-renders from one source.
 */
export function useRegeneratePatternFeedback(gameId: string | undefined, profileId?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => fetchPatternFeedback(gameId as string, profileId, { regenerate: true }),
    onSuccess: (feedback) => {
      queryClient.setQueryData(patternFeedbackKeys.game(gameId ?? '', profileId), feedback);
    },
  });
}
