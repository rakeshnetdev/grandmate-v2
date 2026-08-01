/**
 * The single post-login page (Phase 16a, D-035) — collapses Import/Games/Dashboard/
 * Chat/Memory/Game-Detail into one three-panel workspace. Login gate matches every
 * former page's own prior pattern; everything past that is `WorkspaceShell`.
 */
import { useCurrentUser } from '@/features/auth';
import { SignedOutIntro, WorkspaceShell } from '@/features/workspace';

export function WorkspacePage() {
  const { data: user } = useCurrentUser();

  if (!user) {
    return <SignedOutIntro />;
  }

  return <WorkspaceShell />;
}
