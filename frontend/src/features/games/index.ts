/**
 * Public surface of the `games` feature.
 *
 * Other features import from here, never from internal paths.
 */
export { useGames, useGame, useGameAnalysis, useGamePatterns, gameKeys } from './hooks/useGames';
export { opponentLine } from './lib/format';
export type { GameSummary, GameAnalysis, GamePatterns, MoveEvaluation } from './api/games';
