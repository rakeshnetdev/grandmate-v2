/**
 * Application shell: header + main content outlet (Phase 16a, D-035).
 *
 * Navigation collapsed to just the header (logo, theme, user menu) — Import/Games/
 * Dashboard/Chat/Memory used to each be a nav link to their own page; all five are now
 * panels/tabs inside the single workspace at `/`, so there is nothing left to link to.
 * `<main>` is full-bleed (no `max-w`/padding) so the workspace's three-panel layout can
 * use the full viewport; `WorkspaceShell` sizes itself against the header height below.
 */
import { Crown } from 'lucide-react';
import { Link, Outlet } from 'react-router-dom';

import { UserMenu } from '@/features/auth';
import { DevInsightPanel } from '@/features/devinsight';
import { ThemeToggle } from '@/shared/theme';

export function RootLayout() {
  return (
    <div className="flex h-screen flex-col">
      <header className="h-16 shrink-0 border-b border-border">
        <div className="flex h-full items-center justify-between px-4">
          <Link to="/" className="flex items-center gap-2 text-lg font-semibold tracking-tight">
            {/* Decorative: the wordmark beside it already names the link, so announcing
                the icon too would just repeat it. */}
            <Crown className="h-5 w-5 text-primary" aria-hidden="true" />
            GrandMate
          </Link>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <UserMenu />
          </div>
        </div>
      </header>

      <main className="min-h-0 flex-1 overflow-hidden">
        <Outlet />
      </main>

      {/* Only bundled in development builds — `import.meta.env.DEV` is statically
          replaced, so the panel and its dependencies are tree-shaken out of production. */}
      {import.meta.env.DEV && <DevInsightPanel />}
    </div>
  );
}
