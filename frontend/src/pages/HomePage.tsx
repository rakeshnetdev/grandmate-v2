/**
 * Landing page.
 *
 * Phase 1 placeholder. Phase 2 replaces this with the login entry point, and Phase 8
 * with the profile dashboard.
 */
import { BackendStatusCard } from '@/features/health';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/shared/components/ui/card';

export function HomePage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">GrandMate</h1>
        <p className="mt-1 text-muted-foreground">
          Chess analysis and coaching. Phase 1: engineering foundation.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <BackendStatusCard />

        <Card>
          <CardHeader>
            <CardTitle>Next</CardTitle>
            <CardDescription>Phase 2 — Supabase foundation and identity</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Log in with Lichess, link a Chess.com username, and create profiles.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
