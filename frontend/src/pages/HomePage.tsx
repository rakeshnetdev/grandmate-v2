/**
 * Landing page.
 *
 * Phase 2 placeholder: shows connectivity and, once logged in, the account that was
 * created. Phase 8 replaces the "Next" card with the real profile dashboard.
 */
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
            <CardTitle>Next</CardTitle>
            <CardDescription>Phase 3 — game ingestion</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              {user
                ? 'Upload a PGN or import games once ingestion lands.'
                : 'Log in with Lichess or Chess.com to create your profile.'}
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
