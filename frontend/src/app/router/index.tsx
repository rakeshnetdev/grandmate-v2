/**
 * Route table.
 *
 * One place that maps paths to pages. Feature routes are registered here rather than
 * being scattered, so the permission-sensitive boundaries introduced in Phase 2 —
 * particularly `/players/:profileId` from ADR-0012 — are visible in a single file.
 */
import { createBrowserRouter } from 'react-router-dom';

import { RootLayout } from '@/app/layouts/RootLayout';
import { LoginPage } from '@/pages/LoginPage';
import { NotFoundPage } from '@/pages/NotFoundPage';
import { WorkspacePage } from '@/pages/WorkspacePage';

export const routes = [
  {
    path: '/',
    element: <RootLayout />,
    children: [
      // Phase 16a (D-035): Import/Games/Dashboard/Chat/Memory/Game-Detail were six
      // separate pages; all six are now panels/tabs inside `WorkspacePage`'s single
      // three-panel shell — see the Phase 16a phase report for the retirement notes.
      { index: true, element: <WorkspacePage /> },
      { path: 'login', element: <LoginPage /> },
      // Phase 9:  { path: 'players/:profileId', element: <PlayerPage /> }
      { path: '*', element: <NotFoundPage /> },
    ],
  },
];

export const router = createBrowserRouter(routes);
