/**
 * Feature hook for persona game reports (Phase 9).
 *
 * No polling: unlike engine analysis, a report is generated synchronously within the
 * request (`domain/reports/service.py`'s get-or-generate) — slower than a cached fetch,
 * but there is no background job to wait on.
 */
import { useQuery } from '@tanstack/react-query';

import { fetchGameReport, type PersonaValue } from '../api/reports';

const SELF_KEY = 'self';

export const reportKeys = {
  all: ['reports'] as const,
  game: (gameId: string, persona: PersonaValue, profileId: string | undefined) =>
    [...reportKeys.all, profileId ?? SELF_KEY, gameId, persona] as const,
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
  });
}
