/**
 * List of the caller's imported games, each linking to its analysis view.
 *
 * The "My games" / "Study games" toggle (Phase 8b) is carried in the `profile` URL
 * search param so it survives navigation into a game's detail page and back.
 */
import { useSearchParams } from 'react-router-dom';

import { useCurrentUser } from '@/features/auth';
import { GamesList } from '@/features/games';
import { ProfileToggle } from '@/features/profiles';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/shared/components/ui/card';

export function GamesPage() {
  const { data: user } = useCurrentUser();
  const [searchParams, setSearchParams] = useSearchParams();
  const profileId = searchParams.get('profile') ?? undefined;

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

  function handleProfileChange(nextProfileId: string | undefined) {
    setSearchParams(nextProfileId ? { profile: nextProfileId } : {});
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Your games</h1>
        <p className="mt-1 text-muted-foreground">Pick a game to see its engine analysis.</p>
      </div>

      <ProfileToggle value={profileId} onChange={handleProfileChange} />

      <Card>
        <CardContent className="pt-6">
          <GamesList profileId={profileId} />
        </CardContent>
      </Card>
    </div>
  );
}
