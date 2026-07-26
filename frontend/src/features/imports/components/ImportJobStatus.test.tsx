/**
 * ImportJobStatus tests: renders counts and per-game rejection reasons from a fetched job.
 */
import { screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { renderWithProviders } from '@/test/render';

import { ImportJobStatus } from './ImportJobStatus';

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

describe('ImportJobStatus', () => {
  it('shows import counts once the job loads', async () => {
    mockFetchOnce({
      id: 'job-1',
      kind: 'pgn_import',
      status: 'done',
      progress: { total: 2, imported: 1, duplicates: 1, rejected: [] },
      error: null,
      created_at: '2026-07-26T00:00:00Z',
      completed_at: '2026-07-26T00:00:01Z',
    });

    renderWithProviders(<ImportJobStatus jobId="job-1" />);

    expect(await screen.findByText('Done')).toBeInTheDocument();
    expect(screen.getByText(/1 imported/)).toBeInTheDocument();
    expect(screen.getByText(/1 duplicate/)).toBeInTheDocument();
  });

  it('lists per-game rejection reasons', async () => {
    mockFetchOnce({
      id: 'job-2',
      kind: 'pgn_import',
      status: 'done',
      progress: {
        total: 1,
        imported: 0,
        duplicates: 0,
        rejected: [
          { source: 'a.pgn', index: 0, reason: 'malformed_pgn', detail: 'illegal san: Qxd8' },
        ],
      },
      error: null,
      created_at: '2026-07-26T00:00:00Z',
      completed_at: '2026-07-26T00:00:01Z',
    });

    renderWithProviders(<ImportJobStatus jobId="job-2" />);

    await waitFor(() => {
      expect(screen.getByText(/malformed pgn/)).toBeInTheDocument();
    });
    expect(screen.getByText(/illegal san: Qxd8/)).toBeInTheDocument();
  });

  it('shows the job-level error reason when the job failed', async () => {
    mockFetchOnce({
      id: 'job-3',
      kind: 'pgn_import',
      status: 'failed',
      progress: { total: 0, imported: 0, duplicates: 0, rejected: [] },
      error: { reason: 'too_many_games', found: 100, limit: 60 },
      created_at: '2026-07-26T00:00:00Z',
      completed_at: '2026-07-26T00:00:01Z',
    });

    renderWithProviders(<ImportJobStatus jobId="job-3" />);

    expect(await screen.findByText('too_many_games')).toBeInTheDocument();
    expect(screen.getByText('Failed')).toBeInTheDocument();
  });
});
