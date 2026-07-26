/**
 * Routing smoke tests.
 *
 * Renders through RootLayout so the shell and the route table are both exercised.
 */
import { screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Route, Routes } from 'react-router-dom';

import { RootLayout } from '@/app/layouts/RootLayout';
import { HomePage } from '@/pages/HomePage';
import { NotFoundPage } from '@/pages/NotFoundPage';
import { renderWithProviders } from '@/test/render';

function renderAt(path: string) {
  // The home page renders the health card, which fetches. Park the request so these
  // tests assert on routing rather than on network state.
  vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})));

  return renderWithProviders(
    <Routes>
      <Route path="/" element={<RootLayout />}>
        <Route index element={<HomePage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>,
    { routes: [path] },
  );
}

describe('routing', () => {
  it('renders the home page at /', () => {
    renderAt('/');

    expect(screen.getByRole('heading', { level: 1, name: 'GrandMate' })).toBeInTheDocument();
  });

  it('renders the shell around every route', () => {
    renderAt('/');

    expect(screen.getByRole('banner')).toBeInTheDocument();
    expect(screen.getByRole('contentinfo')).toBeInTheDocument();
  });

  it('renders the not-found page for an unknown route', () => {
    renderAt('/does-not-exist');

    expect(screen.getByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
  });
});
