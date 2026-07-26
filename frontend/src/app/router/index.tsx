/**
 * Route table.
 *
 * One place that maps paths to pages. Feature routes are registered here rather than
 * being scattered, so the permission-sensitive boundaries introduced in Phase 2 —
 * particularly `/players/:profileId` from ADR-0012 — are visible in a single file.
 */
import { createBrowserRouter } from 'react-router-dom';

import { RootLayout } from '@/app/layouts/RootLayout';
import { HomePage } from '@/pages/HomePage';
import { NotFoundPage } from '@/pages/NotFoundPage';

export const routes = [
  {
    path: '/',
    element: <RootLayout />,
    children: [
      { index: true, element: <HomePage /> },
      // Phase 2:  { path: 'auth/callback', element: <AuthCallbackPage /> }
      // Phase 9:  { path: 'players/:profileId', element: <PlayerPage /> }
      { path: '*', element: <NotFoundPage /> },
    ],
  },
];

export const router = createBrowserRouter(routes);
