/**
 * Feature hooks for viewing imported games and their analysis.
 *
 * `useGameAnalysis` polls until analysis exists: Phase 5 queues engine analysis as a
 * background job rather than running it inline (~7s/game, too slow for the import
 * request itself — see `domain/imports/service.py`), so `GET /analysis/games/{id}`
 * genuinely 404s for a little while after import. That 404 is treated as "not ready
 * yet," not an error — same polling shape as `useImportJob`, just keyed off presence of
 * data instead of a status field, since this endpoint has no in-between status of its
 * own.
 *
 * Every hook here accepts an optional `profileId` (Phase 8b) — `undefined` means the
 * caller's own SELF profile, the same default the backend falls back to. It is threaded
 * into each query key so switching between "My games" and "Study games" never shows the
 * other profile's cached data.
 */
import { useQuery } from '@tanstack/react-query';

import { ApiError } from '@/shared/lib/api-client';

import {
  fetchGame,
  fetchGameAnalysis,
  fetchGamePatterns,
  fetchGames,
  type GameAnalysis,
} from '../api/games';

const SELF_KEY = 'self';

export const gameKeys = {
  all: ['games'] as const,
  list: (profileId: string | undefined) =>
    [...gameKeys.all, 'list', profileId ?? SELF_KEY] as const,
  detail: (gameId: string, profileId: string | undefined) =>
    [...gameKeys.all, 'detail', profileId ?? SELF_KEY, gameId] as const,
  analysis: (gameId: string, profileId: string | undefined) =>
    [...gameKeys.all, 'analysis', profileId ?? SELF_KEY, gameId] as const,
  patterns: (gameId: string, profileId: string | undefined) =>
    [...gameKeys.all, 'patterns', profileId ?? SELF_KEY, gameId] as const,
};

const ANALYSIS_POLL_MS = 2000;

export function useGames(profileId?: string) {
  return useQuery({
    queryKey: gameKeys.list(profileId),
    queryFn: ({ signal }) => fetchGames(profileId, signal),
  });
}

export function useGame(gameId: string | undefined, profileId?: string) {
  return useQuery({
    queryKey: gameKeys.detail(gameId ?? '', profileId),
    queryFn: ({ signal }) => fetchGame(gameId as string, profileId, signal),
    enabled: Boolean(gameId),
  });
}

async function fetchGameAnalysisOrNull(
  gameId: string,
  profileId: string | undefined,
  signal?: AbortSignal,
): Promise<GameAnalysis | null> {
  try {
    return await fetchGameAnalysis(gameId, profileId, signal);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

export function useGameAnalysis(gameId: string | undefined, profileId?: string) {
  return useQuery({
    queryKey: gameKeys.analysis(gameId ?? '', profileId),
    queryFn: ({ signal }) => fetchGameAnalysisOrNull(gameId as string, profileId, signal),
    enabled: Boolean(gameId),
    refetchInterval: (query) => (query.state.data ? false : ANALYSIS_POLL_MS),
  });
}

/** Only fetched once analysis is ready — motif/theme findings ride the same background
 * job, so there is nothing new to show before then (see `domain/patterns/service.py`). */
export function useGamePatterns(
  gameId: string | undefined,
  profileId?: string,
  options: { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: gameKeys.patterns(gameId ?? '', profileId),
    queryFn: ({ signal }) => fetchGamePatterns(gameId as string, profileId, signal),
    enabled: Boolean(gameId) && (options.enabled ?? true),
  });
}
