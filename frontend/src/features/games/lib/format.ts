import type { GameSummary } from '../api/games';

/** "White vs Black (Result)" — shared between `GamesList` (Phase 8) and the workspace's
 * `GameListPanel` (Phase 16a) so a game reads identically in both places. */
export function opponentLine(headers: GameSummary['headers']): string {
  const white = headers.White ?? '?';
  const black = headers.Black ?? '?';
  const result = headers.Result ? ` (${headers.Result})` : '';
  return `${white} vs ${black}${result}`;
}
