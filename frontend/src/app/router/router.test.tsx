/**
 * Routing smoke tests.
 *
 * Renders through RootLayout so the shell and the route table are both exercised.
 */
import { screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Route, Routes } from 'react-router-dom';

import { RootLayout } from '@/app/layouts/RootLayout';
import { NotFoundPage } from '@/pages/NotFoundPage';
import { WorkspacePage } from '@/pages/WorkspacePage';
import { renderWithProviders } from '@/test/render';

function renderAt(path: string) {
  // The workspace page's login gate reads the current user, which fetches. Park the
  // request so these tests assert on routing rather than on network state.
  vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})));

  return renderWithProviders(
    <Routes>
      <Route path="/" element={<RootLayout />}>
        <Route index element={<WorkspacePage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>,
    { routes: [path] },
  );
}

describe('routing', () => {
  it('renders the workspace page at /', () => {
    renderAt('/');

    expect(screen.getByRole('heading', { name: 'GrandMate' })).toBeInTheDocument();
  });

  it('renders the shell around every route', () => {
    renderAt('/');

    // No footer (Phase 16a, D-035): the workspace shell fills the viewport under a
    // fixed-height header, and a footer would eat into that height budget for no
    // benefit in an app that has no more content below the fold to summarise.
    expect(screen.getByRole('banner')).toBeInTheDocument();
  });

  it('renders the not-found page for an unknown route', () => {
    renderAt('/does-not-exist');

    expect(screen.getByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
  });
});
