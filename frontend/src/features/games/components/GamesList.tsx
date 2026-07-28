/**
 * List of the caller's imported games, each linking to its analysis view.
 */
import { Link } from 'react-router-dom';

import type { GameSummary } from '../api/games';
import { useGames } from '../hooks/useGames';

function opponentLine(headers: GameSummary['headers']): string {
  const white = headers.White ?? '?';
  const black = headers.Black ?? '?';
  const result = headers.Result ? ` (${headers.Result})` : '';
  return `${white} vs ${black}${result}`;
}

export function GamesList() {
  const { data: games, isLoading } = useGames();

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading games…</p>;
  }

  if (!games || games.length === 0) {
    return <p className="text-sm text-muted-foreground">No games imported yet.</p>;
  }

  return (
    <ul className="space-y-2">
      {games.map((game) => (
        <li key={game.id}>
          <Link
            to={`/games/${game.id}`}
            className="flex items-center justify-between gap-3 rounded-md border border-border p-4 hover:bg-accent"
          >
            <span className="text-sm font-medium">{opponentLine(game.headers)}</span>
            <span className="text-xs text-muted-foreground">
              {game.canonicalized_at ? 'View analysis' : 'Not parsed'}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
