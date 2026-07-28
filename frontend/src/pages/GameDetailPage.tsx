/**
 * One game's analysis: engine evaluation, opening, and tactical/strategic findings.
 *
 * `profile` in the URL search params (Phase 8b) carries which profile this game belongs
 * to, set by `GamesList`'s links — `undefined` means the caller's own SELF profile.
 */
import { Link, useParams, useSearchParams } from 'react-router-dom';

import { GameAnalysisView, useGame } from '@/features/games';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';

export function GameDetailPage() {
  const { gameId } = useParams<{ gameId: string }>();
  const [searchParams] = useSearchParams();
  const profileId = searchParams.get('profile') ?? undefined;
  const { data: game } = useGame(gameId, profileId);

  if (!gameId) {
    return null;
  }

  const white = game?.headers.White ?? '…';
  const black = game?.headers.Black ?? '…';
  const backLink = profileId ? `/games?profile=${profileId}` : '/games';

  return (
    <div className="space-y-6">
      <div>
        <Link to={backLink} className="text-sm text-muted-foreground underline">
          ← Back to your games
        </Link>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>
            {white} vs {black}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <GameAnalysisView gameId={gameId} profileId={profileId} />
        </CardContent>
      </Card>
    </div>
  );
}
