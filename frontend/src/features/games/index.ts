/**
 * Public surface of the `games` feature.
 *
 * Other features import from here, never from internal paths.
 */
export { GamesList } from './components/GamesList';
export { GameAnalysisView } from './components/GameAnalysisView';
export { useGames, useGame, useGameAnalysis, useGamePatterns, gameKeys } from './hooks/useGames';
export type { GameSummary, GameAnalysis, GamePatterns, MoveEvaluation } from './api/games';
