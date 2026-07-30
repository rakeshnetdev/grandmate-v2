/**
 * The single post-login page (Phase 16a, D-035) — collapses Import/Games/Dashboard/
 * Chat/Memory/Game-Detail into one three-panel workspace. Login gate matches every
 * former page's own prior pattern; everything past that is `WorkspaceShell`.
 */
import { useCurrentUser } from '@/features/auth';
import { WorkspaceShell } from '@/features/workspace';
import { Card, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';

export function WorkspacePage() {
  const { data: user } = useCurrentUser();

  if (!user) {
    return (
      <div className="p-6">
        <Card>
          <CardHeader>
            <CardTitle>GrandMate</CardTitle>
            <CardDescription>
              Log in with Lichess or Chess.com to import games, see analysis, and chat about your
              play.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  return <WorkspaceShell />;
}
