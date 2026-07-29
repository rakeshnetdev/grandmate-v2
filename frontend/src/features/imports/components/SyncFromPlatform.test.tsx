/**
 * SyncFromPlatform tests: the sync request it produces, the window selector, and error
 * shaping for the two documented failure statuses (404 unlinked, 422 bad window).
 */
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { renderWithProviders } from '@/test/render';

import { SyncFromPlatform } from './SyncFromPlatform';

const pendingJob = {
  id: 'job-1',
  kind: 'pgn_import',
  status: 'pending',
  progress: { total: 0, imported: 0, duplicates: 0, rejected: [] },
  error: null,
  created_at: '2026-07-29T00:00:00Z',
  completed_at: null,
};

function mockFetchOnce(body: unknown, ok = true, status = ok ? 202 : 422) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok,
    status,
    json: () => Promise.resolve(body),
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('SyncFromPlatform', () => {
  it('requests a sync for the given provider and default window', async () => {
    const fetchMock = mockFetchOnce(pendingJob);
    const user = userEvent.setup();

    renderWithProviders(<SyncFromPlatform provider="lichess" username="magnus" />);
    await user.click(screen.getByRole('button', { name: /Sync from Lichess \(magnus\)/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/imports/lichess/sync'),
        expect.objectContaining({ method: 'POST' }),
      );
    });
    const [, requestInit] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(requestInit.body as string)).toEqual({ window: 10 });
  });

  it('sends the selected window when changed', async () => {
    const fetchMock = mockFetchOnce(pendingJob);
    const user = userEvent.setup();

    renderWithProviders(<SyncFromPlatform provider="chesscom" username="hikaru" />);
    await user.selectOptions(screen.getByLabelText(/Last/i), '30');
    await user.click(screen.getByRole('button', { name: /Sync from Chess.com \(hikaru\)/i }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [, requestInit] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(requestInit.body as string)).toEqual({ window: 30 });
  });

  it('calls onSynced with the pending job once the sync starts', async () => {
    mockFetchOnce(pendingJob);
    const onSynced = vi.fn();
    const user = userEvent.setup();

    renderWithProviders(
      <SyncFromPlatform provider="lichess" username="magnus" onSynced={onSynced} />,
    );
    await user.click(screen.getByRole('button', { name: /Sync from Lichess/i }));

    await waitFor(() => expect(onSynced).toHaveBeenCalledWith(pendingJob));
  });

  it('shows a clear message when there is no linked account for that platform', async () => {
    mockFetchOnce({ detail: 'No linked chesscom account for this profile' }, false, 404);
    const user = userEvent.setup();

    renderWithProviders(<SyncFromPlatform provider="chesscom" username="hikaru" />);
    await user.click(screen.getByRole('button', { name: /Sync from Chess.com/i }));

    expect(
      await screen.findByText(/No linked chesscom account for this profile/),
    ).toBeInTheDocument();
  });
});
