/**
 * Profile analytics dashboard page (Phase 8).
 *
 * The "My games" / "Study games" toggle (Phase 8b) is carried in the `profile` URL
 * search param, same convention as `GamesPage`.
 */
import { useSearchParams } from 'react-router-dom';

import { ProfileDashboard } from '@/features/analytics';
import { useCurrentUser } from '@/features/auth';
import { ProfileToggle } from '@/features/profiles';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/shared/components/ui/card';

export function DashboardPage() {
  const { data: user } = useCurrentUser();
  const [searchParams, setSearchParams] = useSearchParams();
  const profileId = searchParams.get('profile') ?? undefined;

  if (!user) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Your dashboard</CardTitle>
          <CardDescription>Log in with Lichess or Chess.com to see your trends</CardDescription>
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
        <h1 className="text-2xl font-semibold tracking-tight">Your dashboard</h1>
        <p className="mt-1 text-muted-foreground">
          Trends and recurring patterns across your most recently analyzed games.
        </p>
      </div>

      <ProfileToggle value={profileId} onChange={handleProfileChange} />

      <Card>
        <CardContent className="pt-6">
          <ProfileDashboard profileId={profileId} />
        </CardContent>
      </Card>
    </div>
  );
}
