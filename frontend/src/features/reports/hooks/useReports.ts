/**
 * Feature hook for persona game reports (Phase 9).
 *
 * Report *generation* is synchronous within the request (`domain/reports/service.py`'s
 * get-or-generate), so there is no job to wait on there. What these hooks do wait on is
 * the engine analysis the report is built from: that runs as a background job after
 * import, and until it finishes the route answers 404 "no analysis found yet". So the
 * queries poll while — and only while — the error says exactly that, and stop the moment
 * they get a report or a genuine failure.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { fetchGameReport, fetchGameStory, type PersonaValue } from '../api/reports';
import { isAnalysisPending } from '../lib/pending';

/**
 * How often to re-ask while the engine is still working. A game is roughly 7s of
 * analysis and sits behind a bounded-concurrency queue, so a few seconds is responsive
 * without hammering the API for the length of a large import.
 */
const ANALYSIS_POLL_MS = 4000;

/** Retry only the "not analyzed yet" case, and keep retrying it — a real error stops. */
const pollWhilePending = {
  retry: (_failureCount: number, error: unknown) => isAnalysisPending(error),
  retryDelay: ANALYSIS_POLL_MS,
} as const;

const SELF_KEY = 'self';

export const reportKeys = {
  all: ['reports'] as const,
  game: (gameId: string, persona: PersonaValue, profileId: string | undefined) =>
    [...reportKeys.all, profileId ?? SELF_KEY, gameId, persona] as const,
  story: (gameId: string, profileId: string | undefined) =>
    [...reportKeys.all, profileId ?? SELF_KEY, gameId, 'story'] as const,
};

export function useGameReport(
  gameId: string | undefined,
  persona: PersonaValue,
  profileId?: string,
) {
  return useQuery({
    queryKey: reportKeys.game(gameId ?? '', persona, profileId),
    queryFn: ({ signal }) => fetchGameReport(gameId as string, persona, profileId, signal),
    enabled: Boolean(gameId),
    // A report is versioned server-side and only regenerated when the underlying
    // analysis changes, so there is nothing to gain from refetching an already-loaded
    // report on window focus etc.
    staleTime: Infinity,
    ...pollWhilePending,
  });
}

/** Phase 16b: the full opening/middlegame/endgame game-story report — self-learner
 * only, so no persona argument (unlike `useGameReport`). */
export function useGameStory(gameId: string | undefined, profileId?: string) {
  return useQuery({
    queryKey: reportKeys.story(gameId ?? '', profileId),
    queryFn: ({ signal }) => fetchGameStory(gameId as string, profileId, signal),
    enabled: Boolean(gameId),
    staleTime: Infinity,
    ...pollWhilePending,
  });
}

/**
 * The explicit "Regenerate" action for a persona report.
 *
 * A mutation rather than a query refetch, for the same reason `useRegeneratePatternFeedback`
 * is one: it spends an LLM call every time by design, so it must be something the user asks
 * for once — never something a refocus or a remount can trigger. `staleTime: Infinity` on
 * the query above is what guarantees that. The result is written straight into the query's
 * cache so the panel re-renders from a single source.
 */
export function useRegenerateGameReport(
  gameId: string | undefined,
  persona: PersonaValue,
  profileId?: string,
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () =>
      fetchGameReport(gameId as string, persona, profileId, undefined, { regenerate: true }),
    onSuccess: (report) => {
      queryClient.setQueryData(reportKeys.game(gameId ?? '', persona, profileId), report);
    },
  });
}

/** The explicit "Regenerate" action for the game story — same contract as
 * `useRegenerateGameReport`, minus the persona. */
export function useRegenerateGameStory(gameId: string | undefined, profileId?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => fetchGameStory(gameId as string, profileId, undefined, { regenerate: true }),
    onSuccess: (story) => {
      queryClient.setQueryData(reportKeys.story(gameId ?? '', profileId), story);
    },
  });
}
