/**
 * PersonaReportPanel tests: renders a report, defaults to the self-learner persona, and
 * switching personas re-fetches with the new persona (and shows the fallback-source
 * badge when the backend used the deterministic path).
 */
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { renderWithProviders } from '@/test/render';

import { PersonaReportPanel } from './PersonaReportPanel';

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
      const key = `${parsed.pathname}?${parsed.searchParams.get('persona')}`;
      const handler = handlers[key];
      if (!handler) {
        throw new Error(`Unhandled fetch in test: ${key}`);
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

function report(overrides: Record<string, unknown> = {}) {
  return {
    id: 'report-1',
    game_id: 'game-1',
    persona: 'self_learner',
    source: 'llm',
    model: 'gpt-4o-mini',
    analysis_version: 'test',
    summary: 'A close game.',
    findings: [{ fact_ids: ['move-4'], text: 'Your move 4 was a blunder.' }],
    recommendations: ['Review move 4.'],
    grounded: true,
    created_at: '2026-07-28T00:00:00Z',
    ...overrides,
  };
}

describe('PersonaReportPanel', () => {
  it('loads the self-learner report by default', async () => {
    mockFetchRoutes({
      '/api/v1/reports/games/game-1?self_learner': { status: 200, body: report() },
    });

    renderWithProviders(<PersonaReportPanel gameId="game-1" />);

    expect(await screen.findByText('A close game.')).toBeInTheDocument();
    // "blunder" renders as its own highlighted span (Phase 16a's `Prose`), so the
    // finding's full sentence is split across nodes — match on the list item's whole
    // text content rather than one exact text node.
    expect(
      screen.getByText(
        (_, element) =>
          element?.tagName === 'LI' && element.textContent === 'Your move 4 was a blunder.',
      ),
    ).toBeInTheDocument();
    expect(screen.getByText('Review move 4.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Self-learner' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });

  it('shows the AI-generated badge for an LLM-sourced report', async () => {
    mockFetchRoutes({
      '/api/v1/reports/games/game-1?self_learner': { status: 200, body: report() },
    });

    renderWithProviders(<PersonaReportPanel gameId="game-1" />);

    expect(await screen.findByText('AI-generated')).toBeInTheDocument();
  });

  it('shows the deterministic-summary badge for a fallback report', async () => {
    mockFetchRoutes({
      '/api/v1/reports/games/game-1?self_learner': {
        status: 200,
        body: report({ source: 'fallback', model: null }),
      },
    });

    renderWithProviders(<PersonaReportPanel gameId="game-1" />);

    expect(await screen.findByText('Deterministic summary')).toBeInTheDocument();
  });

  it('groups findings under What Went Well / Mistakes & Blunders when kind-tagged', async () => {
    // Phase 16a, D-035 addendum: the self-learner game format tags each finding
    // "strength" or "mistake" — ReportView must group and header them accordingly
    // instead of the flat list coach/kid still get.
    mockFetchRoutes({
      '/api/v1/reports/games/game-1?self_learner': {
        status: 200,
        body: report({
          findings: [
            { fact_ids: ['move-6'], text: "White's Qxe4 was best.", kind: 'strength' },
            { fact_ids: ['move-4'], text: "Black's move 4 was a blunder.", kind: 'mistake' },
          ],
          recommendations: ["Review Black's move 4."],
        }),
      },
    });

    renderWithProviders(<PersonaReportPanel gameId="game-1" />);

    expect(await screen.findByText('What Went Well')).toBeInTheDocument();
    expect(screen.getByText('Mistakes & Blunders')).toBeInTheDocument();
    expect(screen.getByText('Strategy to Improve')).toBeInTheDocument();
    expect(screen.queryByText('Recommendations')).not.toBeInTheDocument();
  });

  it('re-fetches with the new persona when switched', async () => {
    const user = userEvent.setup();
    mockFetchRoutes({
      '/api/v1/reports/games/game-1?self_learner': { status: 200, body: report() },
      '/api/v1/reports/games/game-1?kid': {
        status: 200,
        body: report({ persona: 'kid', summary: 'You did great!' }),
      },
    });

    renderWithProviders(<PersonaReportPanel gameId="game-1" />);
    await screen.findByText('A close game.');

    await user.click(screen.getByRole('button', { name: 'Kid' }));

    expect(await screen.findByText('You did great!')).toBeInTheDocument();
  });

  it('regenerates the loaded report on request', async () => {
    const user = userEvent.setup();
    mockFetchRoutes({
      '/api/v1/reports/games/game-1?self_learner': { status: 200, body: report() },
    });

    renderWithProviders(<PersonaReportPanel gameId="game-1" />);
    await screen.findByText('A close game.');

    await user.click(screen.getByRole('button', { name: 'Regenerate report' }));

    // The regenerate call is the one that carries `regenerate=true`; the initial load
    // must not, or every mount would spend an LLM call.
    const urls = (fetch as unknown as { mock: { calls: [string][] } }).mock.calls.map(
      ([url]) => url,
    );
    expect(urls.some((url) => url.includes('regenerate=true'))).toBe(true);
    expect(urls.filter((url) => url.includes('regenerate=true'))).toHaveLength(1);
  });

  it('still offers a retry when the report could not be loaded at all', async () => {
    // Regression: the error branch rendered only text, so a failed load was a dead end —
    // the refresh control lives on the badge, and a failed load renders no badge.
    mockFetchRoutes({
      '/api/v1/reports/games/game-1?self_learner': { status: 500, body: { detail: 'boom' } },
    });

    renderWithProviders(<PersonaReportPanel gameId="game-1" />);

    expect(await screen.findByText(/Could not load the report/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Regenerate report' })).toBeInTheDocument();
  });
});
