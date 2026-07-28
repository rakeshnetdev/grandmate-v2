/**
 * Landing page.
 *
 * Shows connectivity and, once logged in, the account that was created plus a way into
 * game ingestion, single-game analysis, and the profile dashboard.
 */
import { Link } from 'react-router-dom';

import { useCurrentUser } from '@/features/auth';
import { BackendStatusCard } from '@/features/health';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/shared/components/ui/card';

export function HomePage() {
  const { data: user } = useCurrentUser();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">GrandMate</h1>
        <p className="mt-1 text-muted-foreground">
          {user
            ? `Welcome back, ${user.username}.`
            : 'Chess analysis and coaching. Phase 2: local Postgres and identity.'}
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <BackendStatusCard />

        <Card>
          <CardHeader>
            <CardTitle>Import games</CardTitle>
            <CardDescription>Phase 3 — game ingestion</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              {user ? (
                <>
                  <Link to="/imports" className="font-medium text-primary underline">
                    Upload a PGN or paste one
                  </Link>{' '}
                  to start building your game history.
                </>
              ) : (
                'Log in with Lichess or Chess.com to create your profile.'
              )}
            </p>
          </CardContent>
        </Card>

        {user && (
          <Card>
            <CardHeader>
              <CardTitle>Your games</CardTitle>
              <CardDescription>Engine analysis, opening, and tactical findings</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                <Link to="/games" className="font-medium text-primary underline">
                  See analysis for a game you've imported
                </Link>
                .
              </p>
            </CardContent>
          </Card>
        )}

        {user && (
          <Card>
            <CardHeader>
              <CardTitle>Your dashboard</CardTitle>
              <CardDescription>Phase 8 — trends across your recent games</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                <Link to="/dashboard" className="font-medium text-primary underline">
                  See recurring weaknesses and progress
                </Link>
                .
              </p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
