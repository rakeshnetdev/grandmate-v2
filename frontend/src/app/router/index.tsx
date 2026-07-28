/**
 * Route table.
 *
 * One place that maps paths to pages. Feature routes are registered here rather than
 * being scattered, so the permission-sensitive boundaries introduced in Phase 2 —
 * particularly `/players/:profileId` from ADR-0012 — are visible in a single file.
 */
import { createBrowserRouter } from 'react-router-dom';

import { RootLayout } from '@/app/layouts/RootLayout';
import { ChatPage } from '@/pages/ChatPage';
import { DashboardPage } from '@/pages/DashboardPage';
import { GameDetailPage } from '@/pages/GameDetailPage';
import { GamesPage } from '@/pages/GamesPage';
import { HomePage } from '@/pages/HomePage';
import { ImportsPage } from '@/pages/ImportsPage';
import { LoginPage } from '@/pages/LoginPage';
import { MemoryPage } from '@/pages/MemoryPage';
import { NotFoundPage } from '@/pages/NotFoundPage';

export const routes = [
  {
    path: '/',
    element: <RootLayout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: 'login', element: <LoginPage /> },
      { path: 'imports', element: <ImportsPage /> },
      { path: 'games', element: <GamesPage /> },
      { path: 'games/:gameId', element: <GameDetailPage /> },
      { path: 'dashboard', element: <DashboardPage /> },
      { path: 'chat', element: <ChatPage /> },
      { path: 'memory', element: <MemoryPage /> },
      // Phase 9:  { path: 'players/:profileId', element: <PlayerPage /> }
      { path: '*', element: <NotFoundPage /> },
    ],
  },
];

export const router = createBrowserRouter(routes);
