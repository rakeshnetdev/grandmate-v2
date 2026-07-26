/**
 * Developer insight panel tests.
 *
 * The behaviour worth protecting: closed costs nothing, and a backend without tracing
 * produces a helpful message rather than a broken panel.
 */
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { renderWithProviders } from '@/test/render';

import { DevInsightPanel } from './DevInsightPanel';

const TRACE_SUMMARY = {
  trace_id: 'abc123',
  label: 'GET /health',
  started_at: '2026-07-26T00:00:00Z',
  duration_ms: 12.5,
  status: 'ok',
  span_count: 2,
  total_tokens: 0,
};

const TRACE = {
  ...TRACE_SUMMARY,
  spans: [
    {
      span_id: 's1',
      parent_span_id: null,
      kind: 'http',
      name: 'GET /health',
      started_at: '2026-07-26T00:00:00Z',
      duration_ms: 12.5,
      status: 'ok',
      error: null,
      attributes: { status_code: 200 },
      tokens: null,
    },
    {
      span_id: 's2',
      parent_span_id: 's1',
      kind: 'llm',
      name: 'complete',
      started_at: '2026-07-26T00:00:00Z',
      duration_ms: 8.0,
      status: 'ok',
      error: null,
      attributes: { prompt: '<redacted, 812 chars>' },
      tokens: { prompt_tokens: 800, completion_tokens: 120 },
    },
  ],
  truncated: false,
};

function mockApi() {
  return vi.fn().mockImplementation((url: string) => {
    const body = url.includes('/traces/') ? TRACE : [TRACE_SUMMARY];
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('DevInsightPanel', () => {
  it('fetches nothing while closed', async () => {
    const fetchMock = mockApi();
    vi.stubGlobal('fetch', fetchMock);

    renderWithProviders(<DevInsightPanel />);

    expect(screen.getByRole('button', { name: 'Developer insight' })).toBeInTheDocument();
    // The whole point of the separate endpoint: a closed panel is free.
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('loads the trace list when opened', async () => {
    vi.stubGlobal('fetch', mockApi());

    renderWithProviders(<DevInsightPanel />);
    await userEvent.click(screen.getByRole('button', { name: 'Developer insight' }));

    expect(await screen.findByText('GET /health')).toBeInTheDocument();
    expect(screen.getByText(/2 spans/)).toBeInTheDocument();
  });

  it('shows span timeline and token usage after selecting a trace', async () => {
    vi.stubGlobal('fetch', mockApi());

    renderWithProviders(<DevInsightPanel />);
    await userEvent.click(screen.getByRole('button', { name: 'Developer insight' }));
    await userEvent.click(await screen.findByText('GET /health'));

    expect(await screen.findByText(/800 prompt \+ 120 completion tokens/)).toBeInTheDocument();
    expect(screen.getByText('Timeline')).toBeInTheDocument();
  });

  it('surfaces redaction markers rather than prompt text', async () => {
    vi.stubGlobal('fetch', mockApi());

    renderWithProviders(<DevInsightPanel />);
    await userEvent.click(screen.getByRole('button', { name: 'Developer insight' }));
    await userEvent.click(await screen.findByText('GET /health'));

    expect(await screen.findByText('<redacted, 812 chars>')).toBeInTheDocument();
  });

  it('explains itself when the backend has tracing disabled', async () => {
    // Production backends have no /dev routes at all.
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: () => Promise.resolve({ detail: 'Not Found' }),
      }),
    );

    renderWithProviders(<DevInsightPanel />);
    await userEvent.click(screen.getByRole('button', { name: 'Developer insight' }));

    await waitFor(() => {
      expect(screen.getByText(/disabled on this backend/)).toBeInTheDocument();
    });
    expect(screen.getByText('DEV_INSIGHT_ENABLED=true')).toBeInTheDocument();
  });
});
