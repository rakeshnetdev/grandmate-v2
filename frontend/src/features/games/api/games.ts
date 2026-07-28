/**
 * Games, analysis, and patterns API contract.
 *
 * Schemas mirror `backend/app/schemas/games.py`, `schemas/analysis.py`, and
 * `schemas/patterns.py`. Three separate backend resources, three separate fetch
 * functions — same split as the routes themselves (see `api/routes/patterns.py`'s
 * docstring for why analysis and patterns aren't folded into one call).
 */
import { z } from 'zod';

import { apiClient } from '@/shared/lib/api-client';

export const gameSummarySchema = z.object({
  id: z.string(),
  source: z.string(),
  headers: z.record(z.string(), z.string()),
  played_at: z.string().nullable(),
  canonicalized_at: z.string().nullable(),
  created_at: z.string(),
});
export type GameSummary = z.infer<typeof gameSummarySchema>;

const moveEvaluationSchema = z.object({
  ply: z.number(),
  eval_cp: z.number().nullable(),
  mate_in: z.number().nullable(),
  best_move_uci: z.string().nullable(),
  pv: z.array(z.string()),
  classification: z.enum(['best', 'good', 'inaccuracy', 'mistake', 'blunder']),
  eval_swing_cp: z.number(),
  is_critical_moment: z.boolean(),
  deep_analyzed: z.boolean(),
});
export type MoveEvaluation = z.infer<typeof moveEvaluationSchema>;

const analysisSummarySchema = z.object({
  total_moves: z.number(),
  counts: z.record(z.string(), z.number()),
  accuracy: z.number(),
  critical_moments: z.number(),
});
export type AnalysisSummary = z.infer<typeof analysisSummarySchema>;

export const gameAnalysisSchema = z.object({
  id: z.string(),
  game_id: z.string(),
  analysis_version: z.string(),
  engine_depth: z.number(),
  summary: analysisSummarySchema,
  completed_at: z.string().nullable(),
  moves: z.array(moveEvaluationSchema),
});
export type GameAnalysis = z.infer<typeof gameAnalysisSchema>;

const openingMatchSchema = z.object({
  eco: z.string(),
  opening_name: z.string(),
  epd: z.string(),
  matched_ply: z.number(),
});

const motifFindingSchema = z.object({
  ply: z.number(),
  side: z.enum(['white', 'black']),
  motif: z.string(),
  confidence: z.number(),
  evidence: z.record(z.string(), z.unknown()),
});

const themeFindingSchema = z.object({
  ply: z.number(),
  side: z.enum(['white', 'black']),
  theme: z.string(),
  confidence: z.number(),
  evidence: z.record(z.string(), z.unknown()),
});

export const gamePatternsSchema = z.object({
  game_id: z.string(),
  opening: openingMatchSchema.nullable(),
  motifs: z.array(motifFindingSchema),
  themes: z.array(themeFindingSchema),
});
export type GamePatterns = z.infer<typeof gamePatternsSchema>;

const gameListSchema = z.array(gameSummarySchema);

/** Appends `?profile_id=` when viewing a profile other than the caller's own SELF
 * profile (Phase 8b) — `undefined` means "use the server's default", not "no profile". */
function withProfileParam(path: string, profileId: string | undefined): string {
  return profileId ? `${path}?profile_id=${profileId}` : path;
}

export function fetchGames(profileId?: string, signal?: AbortSignal): Promise<GameSummary[]> {
  return apiClient.get(withProfileParam('/api/v1/games', profileId), gameListSchema, signal);
}

export function fetchGame(
  gameId: string,
  profileId?: string,
  signal?: AbortSignal,
): Promise<GameSummary> {
  return apiClient.get(
    withProfileParam(`/api/v1/games/${gameId}`, profileId),
    gameSummarySchema,
    signal,
  );
}

export function fetchGameAnalysis(
  gameId: string,
  profileId?: string,
  signal?: AbortSignal,
): Promise<GameAnalysis> {
  return apiClient.get(
    withProfileParam(`/api/v1/analysis/games/${gameId}`, profileId),
    gameAnalysisSchema,
    signal,
  );
}

export function fetchGamePatterns(
  gameId: string,
  profileId?: string,
  signal?: AbortSignal,
): Promise<GamePatterns> {
  return apiClient.get(
    withProfileParam(`/api/v1/patterns/games/${gameId}`, profileId),
    gamePatternsSchema,
    signal,
  );
}
