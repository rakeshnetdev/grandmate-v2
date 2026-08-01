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
import { useQuery } from '@tanstack/react-query';

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
