/**
 * Application shell: header, main content outlet, footer.
 *
 * Navigation grows here as features land. Kept structural — no data fetching.
 */
import { Link, Outlet } from 'react-router-dom';

import { UserMenu } from '@/features/auth';
import { DevInsightPanel } from '@/features/devinsight';

export function RootLayout() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-border">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <Link to="/" className="text-lg font-semibold tracking-tight">
            GrandMate
          </Link>
          <nav className="flex items-center gap-4 text-sm text-muted-foreground">
            <Link to="/imports" className="hover:text-foreground">
              Import
            </Link>
            <Link to="/games" className="hover:text-foreground">
              Games
            </Link>
            <UserMenu />
          </nav>
        </div>
      </header>

      <main className="mx-auto w-full max-w-5xl flex-1 px-6 py-8">
        <Outlet />
      </main>

      {/* Only bundled in development builds — `import.meta.env.DEV` is statically
          replaced, so the panel and its dependencies are tree-shaken out of production. */}
      {import.meta.env.DEV && <DevInsightPanel />}

      <footer className="border-t border-border">
        <div className="mx-auto max-w-5xl px-6 py-4 text-sm text-muted-foreground">
          Chess analysis and coaching
        </div>
      </footer>
    </div>
  );
}
