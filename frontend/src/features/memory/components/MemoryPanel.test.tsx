/**
 * MemoryPanel tests: empty state, listing, and deleting a memory (Phase 11).
 * Write-path correctness (confidence floor, supersession) is a backend concern.
 */
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { renderWithProviders } from '@/test/render';

import { MemoryPanel } from './MemoryPanel';

interface RouteHandler {
  status: number;
  body: unknown;
}

function mockFetchRoutes(handlers: Record<string, () => RouteHandler>) {
  vi.stubGlobal(
    'fetch',
    vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString();
      const parsed = new URL(url, 'http://localhost');
      const key = `${init?.method ?? 'GET'} ${parsed.pathname}`;
      const handler = handlers[key];
      if (!handler) {
        throw new Error(`Unhandled fetch in test: ${key}`);
      }
      const { status, body } = handler();
      return Promise.resolve({
        ok: status < 400,
        status,
        json: () => Promise.resolve(body),
      });
    }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

const memory = {
  id: 'mem-1',
  kind: 'goal',
  content: 'Wants to improve endgames',
  confidence: 0.9,
  source_thread_id: null,
  created_at: '2026-07-28T00:00:00Z',
  superseded_at: null,
};

describe('MemoryPanel', () => {
  it('shows the empty state when nothing is remembered', async () => {
    mockFetchRoutes({ 'GET /api/v1/memory': () => ({ status: 200, body: [] }) });

    renderWithProviders(<MemoryPanel />);

    expect(await screen.findByText(/Nothing remembered yet/)).toBeInTheDocument();
  });

  it('lists an active memory with its kind label', async () => {
    mockFetchRoutes({ 'GET /api/v1/memory': () => ({ status: 200, body: [memory] }) });

    renderWithProviders(<MemoryPanel />);

    expect(await screen.findByText('Wants to improve endgames')).toBeInTheDocument();
    expect(screen.getByText('Goal')).toBeInTheDocument();
  });

  it('shows a superseded memory as inactive, with no delete button', async () => {
    mockFetchRoutes({
      'GET /api/v1/memory': () => ({
        status: 200,
        body: [{ ...memory, superseded_at: '2026-07-29T00:00:00Z' }],
      }),
    });

    renderWithProviders(<MemoryPanel />);

    expect(await screen.findByText('No longer active')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Forget' })).not.toBeInTheDocument();
  });

  it('removes a memory from the list once deleted', async () => {
    let deleted = false;
    mockFetchRoutes({
      'GET /api/v1/memory': () => ({
        status: 200,
        body: deleted ? [] : [memory],
      }),
      'DELETE /api/v1/memory/mem-1': () => {
        deleted = true;
        return { status: 204, body: undefined };
      },
    });
    const user = userEvent.setup();

    renderWithProviders(<MemoryPanel />);
    await user.click(await screen.findByRole('button', { name: 'Forget' }));

    expect(await screen.findByText(/Nothing remembered yet/)).toBeInTheDocument();
  });
});
