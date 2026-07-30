/**
 * `GameListPanel` tests (Phase 16a): collapsed vs. expanded rendering, and selection
 * (click-to-select, not navigation — the key behavioural difference from the retired
 * `GamesList` this replaces).
 */
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { renderWithProviders } from '@/test/render';

import { GameListPanel } from './GameListPanel';

interface RouteHandler {
  status: number;
  body: unknown;
}

function mockFetchRoutes(handlers: Record<string, RouteHandler>) {
  vi.stubGlobal(
    'fetch',
    vi.fn((input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();
      const parsed = new URL(url, 'http://localhost');
      const handler = handlers[parsed.pathname];
      if (!handler) {
        throw new Error(`Unhandled fetch in test: ${parsed.pathname}`);
      }
      return Promise.resolve({
        ok: handler.status < 400,
        status: handler.status,
        json: () => Promise.resolve(handler.body),
      });
    }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

const GAMES = [
  {
    id: 'game-1',
    source: 'upload',
    headers: { White: 'Alice', Black: 'Bob', Result: '1-0' },
    played_at: null,
    canonicalized_at: '2026-07-29T00:00:00Z',
    created_at: '2026-07-29T00:00:00Z',
  },
];

describe('GameListPanel', () => {
  it('shows only an icon rail when collapsed', () => {
    mockFetchRoutes({ '/api/v1/games': { status: 200, body: GAMES } });

    renderWithProviders(
      <GameListPanel onSelectGame={() => {}} collapsed onToggleCollapsed={() => {}} />,
    );

    expect(screen.queryByText('Games')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Expand game list' })).toBeInTheDocument();
  });

  it('lists games and calls onSelectGame when one is clicked', async () => {
    mockFetchRoutes({ '/api/v1/games': { status: 200, body: GAMES } });
    const user = userEvent.setup();
    const onSelectGame = vi.fn();

    renderWithProviders(
      <GameListPanel onSelectGame={onSelectGame} collapsed={false} onToggleCollapsed={() => {}} />,
    );

    const gameButton = await screen.findByText('Alice vs Bob (1-0)');
    await user.click(gameButton);

    expect(onSelectGame).toHaveBeenCalledWith('game-1');
  });

  it('shows an empty state when there are no games', async () => {
    mockFetchRoutes({ '/api/v1/games': { status: 200, body: [] } });

    renderWithProviders(
      <GameListPanel onSelectGame={() => {}} collapsed={false} onToggleCollapsed={() => {}} />,
    );

    expect(await screen.findByText(/No games imported yet/)).toBeInTheDocument();
  });

  it('opens the import modal from the Import button', async () => {
    mockFetchRoutes({
      '/api/v1/games': { status: 200, body: GAMES },
      '/api/v1/auth/me': { status: 401, body: { detail: 'not logged in' } },
    });
    const user = userEvent.setup();

    renderWithProviders(
      <GameListPanel onSelectGame={() => {}} collapsed={false} onToggleCollapsed={() => {}} />,
    );

    await user.click(screen.getByRole('button', { name: /Import/ }));

    expect(await screen.findByRole('dialog', { name: 'Import games' })).toBeInTheDocument();
  });
});
