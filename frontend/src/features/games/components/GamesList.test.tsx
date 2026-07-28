/**
 * GamesList tests: renders each game's opponent line and links to its detail page.
 */
import { screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { renderWithProviders } from '@/test/render';

import { GamesList } from './GamesList';

function mockFetchOnce(body: unknown) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(body),
    }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('GamesList', () => {
  it('shows a message when there are no games yet', async () => {
    mockFetchOnce([]);

    renderWithProviders(<GamesList />);

    expect(await screen.findByText('No games imported yet.')).toBeInTheDocument();
  });

  it('lists each game with an opponent line and a link to its analysis', async () => {
    mockFetchOnce([
      {
        id: 'game-1',
        source: 'upload',
        headers: { White: 'Alice', Black: 'Bob', Result: '1-0' },
        played_at: null,
        canonicalized_at: '2026-07-27T00:00:00Z',
        created_at: '2026-07-27T00:00:00Z',
      },
      {
        id: 'game-2',
        source: 'upload',
        headers: { White: 'Carol', Black: 'Dave', Result: '0-1' },
        played_at: null,
        canonicalized_at: null,
        created_at: '2026-07-26T00:00:00Z',
      },
    ]);

    renderWithProviders(<GamesList />);

    expect(await screen.findByText('Alice vs Bob (1-0)')).toBeInTheDocument();
    expect(screen.getByText('Carol vs Dave (0-1)')).toBeInTheDocument();
    expect(screen.getByText('View analysis')).toBeInTheDocument();
    expect(screen.getByText('Not parsed')).toBeInTheDocument();

    const links = screen.getAllByRole('link');
    expect(links.map((link) => link.getAttribute('href'))).toEqual([
      '/games/game-1',
      '/games/game-2',
    ]);
  });

  it('carries the profile id into both the fetch and the game links (Phase 8b)', async () => {
    let requestedUrl = '';
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        requestedUrl = typeof input === 'string' ? input : input.toString();
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () =>
            Promise.resolve([
              {
                id: 'game-1',
                source: 'upload',
                headers: { White: 'Alice', Black: 'Bob', Result: '1-0' },
                played_at: null,
                canonicalized_at: '2026-07-27T00:00:00Z',
                created_at: '2026-07-27T00:00:00Z',
              },
            ]),
        });
      }),
    );

    renderWithProviders(<GamesList profileId="study-1" />);

    expect(await screen.findByRole('link')).toHaveAttribute(
      'href',
      '/games/game-1?profile=study-1',
    );
    expect(requestedUrl).toContain('profile_id=study-1');
  });
});
