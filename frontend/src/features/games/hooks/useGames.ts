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

export const gameKeys = {
  all: ['games'] as const,
  list: () => [...gameKeys.all, 'list'] as const,
  detail: (gameId: string) => [...gameKeys.all, 'detail', gameId] as const,
  analysis: (gameId: string) => [...gameKeys.all, 'analysis', gameId] as const,
  patterns: (gameId: string) => [...gameKeys.all, 'patterns', gameId] as const,
};

const ANALYSIS_POLL_MS = 2000;

export function useGames() {
  return useQuery({
    queryKey: gameKeys.list(),
    queryFn: ({ signal }) => fetchGames(signal),
  });
}

export function useGame(gameId: string | undefined) {
  return useQuery({
    queryKey: gameKeys.detail(gameId ?? ''),
    queryFn: ({ signal }) => fetchGame(gameId as string, signal),
    enabled: Boolean(gameId),
  });
}

async function fetchGameAnalysisOrNull(
  gameId: string,
  signal?: AbortSignal,
): Promise<GameAnalysis | null> {
  try {
    return await fetchGameAnalysis(gameId, signal);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

export function useGameAnalysis(gameId: string | undefined) {
  return useQuery({
    queryKey: gameKeys.analysis(gameId ?? ''),
    queryFn: ({ signal }) => fetchGameAnalysisOrNull(gameId as string, signal),
    enabled: Boolean(gameId),
    refetchInterval: (query) => (query.state.data ? false : ANALYSIS_POLL_MS),
  });
}

/** Only fetched once analysis is ready — motif/theme findings ride the same background
 * job, so there is nothing new to show before then (see `domain/patterns/service.py`). */
export function useGamePatterns(gameId: string | undefined, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: gameKeys.patterns(gameId ?? ''),
    queryFn: ({ signal }) => fetchGamePatterns(gameId as string, signal),
    enabled: Boolean(gameId) && (options.enabled ?? true),
  });
}
