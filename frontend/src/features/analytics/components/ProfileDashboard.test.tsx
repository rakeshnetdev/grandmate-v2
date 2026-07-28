/**
 * ProfileDashboard tests: empty state, populated state (stat tiles, tables, weakness
 * list), the insufficient-sample banner, and switching windows re-fetches with the new
 * window size.
 */
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { renderWithProviders } from '@/test/render';

import { ProfileDashboard } from './ProfileDashboard';

function mockFetchByWindow(bodies: Record<number, unknown>) {
  vi.stubGlobal(
    'fetch',
    vi.fn((input: RequestInfo | URL) => {
      const url = new URL(typeof input === 'string' ? input : input.toString(), 'http://localhost');
      const window = Number(url.searchParams.get('window'));
      const body = bodies[window];
      if (body === undefined) {
        throw new Error(`Unhandled fetch in test for window=${window}`);
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve(body),
      });
    }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

const EMPTY_SNAPSHOT = {
  profile_id: 'profile-1',
  window_size: 10,
  games_included: 0,
  sufficient_sample: false,
  snapshot_version: 'agg-v1',
  computed_at: '2026-07-27T00:00:00Z',
  accuracy: { current: null, previous: null, delta: null },
  classification_rates: { current: {}, previous: {}, delta: null },
  critical_moment_rate: { current: null, previous: null, delta: null },
  opening_family_performance: [],
  color_segmentation: [],
  time_control_segmentation: [],
  recurring_weaknesses: [],
};

const POPULATED_SNAPSHOT = {
  profile_id: 'profile-1',
  window_size: 10,
  games_included: 3,
  sufficient_sample: false,
  snapshot_version: 'agg-v1',
  computed_at: '2026-07-27T00:00:00Z',
  accuracy: { current: 88.5, previous: 80.0, delta: 8.5 },
  classification_rates: {
    current: { best: 0.6, good: 0.3, inaccuracy: 0.05, mistake: 0.03, blunder: 0.02 },
    previous: { best: 0.5, good: 0.3, inaccuracy: 0.1, mistake: 0.05, blunder: 0.05 },
    delta: { best: 0.1, good: 0.0, inaccuracy: -0.05, mistake: -0.02, blunder: -0.03 },
  },
  critical_moment_rate: { current: 1.5, previous: 2.0, delta: -0.5 },
  opening_family_performance: [
    {
      family: 'Ruy Lopez',
      games: 2,
      wins: 1,
      draws: 0,
      losses: 1,
      win_rate: 0.5,
      average_accuracy: 85.0,
    },
  ],
  color_segmentation: [
    { color: 'white', games: 2, average_accuracy: 90.0, classification_rates: {}, win_rate: 0.5 },
  ],
  time_control_segmentation: [
    { bucket: 'blitz', games: 3, average_accuracy: 91.2, win_rate: 0.33 },
  ],
  recurring_weaknesses: [
    { kind: 'motif', name: 'hanging_piece', games_with_finding: 2, occurrence_rate: 0.667 },
  ],
};

describe('ProfileDashboard', () => {
  it('shows a message when there are no analyzed games yet', async () => {
    mockFetchByWindow({ 10: EMPTY_SNAPSHOT });

    renderWithProviders(<ProfileDashboard />);

    expect(await screen.findByText(/No analyzed games yet/)).toBeInTheDocument();
  });

  it('renders stat tiles, tables, and the weakness list once data loads', async () => {
    mockFetchByWindow({ 10: POPULATED_SNAPSHOT });

    renderWithProviders(<ProfileDashboard />);

    expect(await screen.findByText('88.5%')).toBeInTheDocument();
    expect(screen.getByText(/\+8.5 pts vs\. prior window/)).toBeInTheDocument();
    expect(screen.getByText('Ruy Lopez')).toBeInTheDocument();
    expect(screen.getByText('Hanging Piece')).toBeInTheDocument();
    expect(screen.getByText(/2 of the window's games/)).toBeInTheDocument();
  });

  it('shows the sample-size banner when the snapshot is not yet confident', async () => {
    mockFetchByWindow({ 10: POPULATED_SNAPSHOT });

    renderWithProviders(<ProfileDashboard />);

    expect(await screen.findByText(/Only 3 analyzed games in this window/)).toBeInTheDocument();
  });

  it('re-fetches with the new window size when a different button is clicked', async () => {
    const user = userEvent.setup();
    mockFetchByWindow({
      10: POPULATED_SNAPSHOT,
      30: { ...POPULATED_SNAPSHOT, window_size: 30, games_included: 12, sufficient_sample: true },
    });

    renderWithProviders(<ProfileDashboard />);
    await screen.findByText('88.5%');

    await user.click(screen.getByRole('button', { name: 'Last 30' }));

    await waitFor(() => {
      expect(screen.queryByText(/Only 3 analyzed games/)).not.toBeInTheDocument();
    });
  });
});
