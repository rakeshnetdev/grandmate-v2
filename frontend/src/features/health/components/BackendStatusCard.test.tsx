/**
 * Smoke tests for the health feature.
 *
 * These exercise the whole frontend chain — component to hook to API module to client —
 * with only `fetch` mocked, which is what makes them worth having in Phase 1.
 */
import { screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { renderWithProviders } from '@/test/render';

import { BackendStatusCard } from './BackendStatusCard';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('BackendStatusCard', () => {
  it('shows a checking state before the request resolves', () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})));

    renderWithProviders(<BackendStatusCard />);

    expect(screen.getByText('Checking…')).toBeInTheDocument();
  });

  it('renders service details once healthy', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve({ status: 'ok', service: 'grandmate-backend', version: '0.1.0' }),
      }),
    );

    renderWithProviders(<BackendStatusCard />);

    expect(await screen.findByText('grandmate-backend')).toBeInTheDocument();
    expect(screen.getByText('0.1.0')).toBeInTheDocument();
  });

  it('gives an actionable message when the backend is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));

    renderWithProviders(<BackendStatusCard />);

    await waitFor(() => {
      expect(screen.getByText(/Unreachable/)).toBeInTheDocument();
    });
    // The message should tell the reader what to do, not just that something broke.
    expect(screen.getByText(/uv run uvicorn/)).toBeInTheDocument();
  });
});
