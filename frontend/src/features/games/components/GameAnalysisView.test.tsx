/**
 * GameAnalysisView tests: the pending state (analysis not ready yet), the ready state
 * (evaluation, opening, and motifs rendered), and the unparsed-game state.
 */
import { screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { renderWithProviders } from '@/test/render';

import { GameAnalysisView } from './GameAnalysisView';

interface RouteHandler {
  status: number;
  body: unknown;
}

function mockFetchRoutes(handlers: Record<string, RouteHandler>) {
  vi.stubGlobal(
    'fetch',
    vi.fn((input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();
      const path = new URL(url, 'http://localhost').pathname;
      const handler = handlers[path];
      if (!handler) {
        throw new Error(`Unhandled fetch in test: ${path}`);
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

const GAME = {
  id: 'game-1',
  source: 'upload',
  headers: { White: 'Alice', Black: 'Bob', Result: '1-0' },
  played_at: null,
  canonicalized_at: '2026-07-27T00:00:00Z',
  created_at: '2026-07-27T00:00:00Z',
};

describe('GameAnalysisView', () => {
  it('shows a pending message while the background analysis job has not finished', async () => {
    mockFetchRoutes({
      '/api/v1/games/game-1': { status: 200, body: GAME },
      '/api/v1/analysis/games/game-1': { status: 404, body: { detail: 'not found' } },
    });

    renderWithProviders(<GameAnalysisView gameId="game-1" />);

    expect(await screen.findByText(/Analyzing this game with Stockfish/)).toBeInTheDocument();
  });

  it('renders evaluation, opening, and motifs once analysis is ready', async () => {
    mockFetchRoutes({
      '/api/v1/games/game-1': { status: 200, body: GAME },
      '/api/v1/analysis/games/game-1': {
        status: 200,
        body: {
          id: 'analysis-1',
          game_id: 'game-1',
          analysis_version: 'test',
          engine_depth: 12,
          summary: {
            total_moves: 2,
            counts: { best: 1, good: 0, inaccuracy: 0, mistake: 1, blunder: 0 },
            accuracy: 50,
            critical_moments: 1,
          },
          completed_at: '2026-07-27T00:00:05Z',
          moves: [
            {
              ply: 1,
              eval_cp: 30,
              mate_in: null,
              best_move_uci: 'e2e4',
              pv: ['e2e4'],
              classification: 'best',
              eval_swing_cp: 0,
              is_critical_moment: false,
              deep_analyzed: false,
            },
            {
              ply: 2,
              eval_cp: -180,
              mate_in: null,
              best_move_uci: 'e7e5',
              pv: ['e7e5'],
              classification: 'mistake',
              eval_swing_cp: 210,
              is_critical_moment: true,
              deep_analyzed: true,
            },
          ],
        },
      },
      '/api/v1/patterns/games/game-1': {
        status: 200,
        body: {
          game_id: 'game-1',
          opening: { eco: 'C60', opening_name: 'Ruy Lopez', epd: 'fen', matched_ply: 4 },
          motifs: [{ ply: 2, side: 'black', motif: 'fork', confidence: 0.9, evidence: {} }],
          themes: [],
        },
      },
    });

    renderWithProviders(<GameAnalysisView gameId="game-1" />);

    expect(await screen.findByText('50% accuracy')).toBeInTheDocument();
    expect(await screen.findByText('Ruy Lopez')).toBeInTheDocument();
    expect(screen.getByText(/fork \(ply 2\)/)).toBeInTheDocument();
    expect(screen.getByText('Best')).toBeInTheDocument();
    expect(screen.getByText('Mistake')).toBeInTheDocument();
    expect(screen.getByText('best: e2e4')).toBeInTheDocument();
  });

  it('shows a message instead of analysis when the game failed to parse', async () => {
    mockFetchRoutes({
      '/api/v1/games/game-1': { status: 200, body: { ...GAME, canonicalized_at: null } },
      '/api/v1/analysis/games/game-1': { status: 404, body: { detail: 'not found' } },
    });

    renderWithProviders(<GameAnalysisView gameId="game-1" />);

    expect(await screen.findByText(/This game could not be parsed/)).toBeInTheDocument();
  });
});
