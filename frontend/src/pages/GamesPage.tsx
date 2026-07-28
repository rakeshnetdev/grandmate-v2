/**
 * List of the caller's imported games, each linking to its analysis view.
 */
import { useCurrentUser } from '@/features/auth';
import { GamesList } from '@/features/games';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/shared/components/ui/card';

export function GamesPage() {
  const { data: user } = useCurrentUser();

  if (!user) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Your games</CardTitle>
          <CardDescription>Log in with Lichess or Chess.com to see your games</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Your games</h1>
        <p className="mt-1 text-muted-foreground">Pick a game to see its engine analysis.</p>
      </div>

      <Card>
        <CardContent className="pt-6">
          <GamesList />
        </CardContent>
      </Card>
    </div>
  );
}
