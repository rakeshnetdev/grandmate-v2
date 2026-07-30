/**
 * TrainingPlanPanel tests: the stored plan is restored on mount (the endpoint is
 * get-or-generate, so this is free when one already exists), an explicit click
 * regenerates for the selected persona and given window, and the source-transparency
 * badge reflects the backend's `source`.
 */
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { renderWithProviders } from '@/test/render';

import { TrainingPlanPanel } from './TrainingPlanPanel';

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
      const regenerate = parsed.searchParams.get('regenerate') ? '&regenerate=true' : '';
      const key = `${parsed.pathname}?persona=${parsed.searchParams.get(
        'persona',
      )}&window=${parsed.searchParams.get('window')}${regenerate}`;
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

function plan(overrides: Record<string, unknown> = {}) {
  return {
    id: 'plan-1',
    profile_id: 'profile-1',
    persona: 'self_learner',
    window_size: 10,
    source: 'llm',
    model: 'gpt-4o-mini',
    snapshot_version: 'agg-v1',
    summary: 'A recurring pattern to work on.',
    findings: [{ fact_ids: ['weakness-motif-fork'], text: 'You keep getting forked.' }],
    recommendations: ['Study fork patterns this week.'],
    themes_covered: ['fork'],
    grounded: true,
    created_at: '2026-07-28T00:00:00Z',
    ...overrides,
  };
}

describe('TrainingPlanPanel', () => {
  it('restores the stored plan on mount without the user clicking anything', async () => {
    mockFetchRoutes({
      '/api/v1/reports/profile/training?persona=self_learner&window=10': {
        status: 200,
        body: plan(),
      },
    });

    renderWithProviders(<TrainingPlanPanel windowSize={10} />);

    expect(await screen.findByText('A recurring pattern to work on.')).toBeInTheDocument();
    expect(screen.getByText('Study fork patterns this week.')).toBeInTheDocument();
    // A plan is already showing, so the action is a regeneration, not a first generate.
    expect(await screen.findByRole('button', { name: 'Regenerate' })).toBeInTheDocument();
  });

  it('sends regenerate=true when the user asks for a new plan', async () => {
    const user = userEvent.setup();
    mockFetchRoutes({
      '/api/v1/reports/profile/training?persona=self_learner&window=10': {
        status: 200,
        body: plan(),
      },
      '/api/v1/reports/profile/training?persona=self_learner&window=10&regenerate=true': {
        status: 200,
        body: plan({ id: 'plan-2', summary: 'A freshly regenerated plan.' }),
      },
    });

    renderWithProviders(<TrainingPlanPanel windowSize={10} />);
    await user.click(await screen.findByRole('button', { name: 'Regenerate' }));

    expect(await screen.findByText('A freshly regenerated plan.')).toBeInTheDocument();
  });

  it('shows the deterministic-summary badge for a fallback plan', async () => {
    mockFetchRoutes({
      '/api/v1/reports/profile/training?persona=self_learner&window=10': {
        status: 200,
        body: plan({ source: 'fallback', model: null }),
      },
    });

    renderWithProviders(<TrainingPlanPanel windowSize={10} />);

    expect(await screen.findByText('Deterministic summary')).toBeInTheDocument();
  });

  it('loads the plan for the selected persona and the window it was given', async () => {
    const user = userEvent.setup();
    mockFetchRoutes({
      '/api/v1/reports/profile/training?persona=self_learner&window=30': {
        status: 200,
        body: plan({ window_size: 30 }),
      },
      '/api/v1/reports/profile/training?persona=kid&window=30': {
        status: 200,
        body: plan({ persona: 'kid', window_size: 30, summary: 'Great job noticing forks!' }),
      },
    });

    renderWithProviders(<TrainingPlanPanel windowSize={30} />);
    await user.click(screen.getByRole('button', { name: 'Kid' }));

    expect(await screen.findByText('Great job noticing forks!')).toBeInTheDocument();
  });
});
