/**
 * One game's analysis: engine evaluation, opening, and tactical/strategic findings.
 */
import { Link, useParams } from 'react-router-dom';

import { GameAnalysisView, useGame } from '@/features/games';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';

export function GameDetailPage() {
  const { gameId } = useParams<{ gameId: string }>();
  const { data: game } = useGame(gameId);

  if (!gameId) {
    return null;
  }

  const white = game?.headers.White ?? '…';
  const black = game?.headers.Black ?? '…';

  return (
    <div className="space-y-6">
      <div>
        <Link to="/games" className="text-sm text-muted-foreground underline">
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
          <GameAnalysisView gameId={gameId} />
        </CardContent>
      </Card>
    </div>
  );
}
