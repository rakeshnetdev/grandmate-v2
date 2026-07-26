/**
 * UploadForm tests: paste text, file selection, and the multipart request they produce.
 */
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { renderWithProviders } from '@/test/render';

import { UploadForm } from './UploadForm';

const doneJob = {
  id: 'job-1',
  kind: 'pgn_import',
  status: 'done',
  progress: { total: 1, imported: 1, duplicates: 0, rejected: [] },
  error: null,
  created_at: '2026-07-26T00:00:00Z',
  completed_at: '2026-07-26T00:00:01Z',
};

function mockFetchOnce(body: unknown, ok = true, status = ok ? 201 : 422) {
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

describe('UploadForm', () => {
  it('submits pasted PGN text as multipart form data', async () => {
    const fetchMock = mockFetchOnce(doneJob);
    const user = userEvent.setup();

    renderWithProviders(<UploadForm />);
    await user.type(screen.getByLabelText(/Paste PGN/i), '1. e4 e5');
    await user.click(screen.getByRole('button', { name: /Import games/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/imports'),
        expect.objectContaining({ method: 'POST' }),
      );
    });
    const [, requestInit] = fetchMock.mock.calls[0] as [string, RequestInit];
    const sentBody = requestInit.body as FormData;
    expect(sentBody).toBeInstanceOf(FormData);
    expect(sentBody.get('pgn_text')).toBe('1. e4 e5');
    // FormData sets its own multipart Content-Type with a boundary — the client must not
    // override it with 'application/json'.
    expect(requestInit.headers).toBeUndefined();
  });

  it('calls onImported and clears the form once the import succeeds', async () => {
    mockFetchOnce(doneJob);
    const onImported = vi.fn();
    const user = userEvent.setup();

    renderWithProviders(<UploadForm onImported={onImported} />);
    const textarea = screen.getByLabelText(/Paste PGN/i);
    await user.type(textarea, '1. e4 e5');
    await user.click(screen.getByRole('button', { name: /Import games/i }));

    await waitFor(() => expect(onImported).toHaveBeenCalledWith(doneJob));
    expect(textarea).toHaveValue('');
  });

  it('shows the server error message on a 422', async () => {
    mockFetchOnce({ detail: 'Provide pasted PGN text or at least one file' }, false, 422);
    const user = userEvent.setup();

    renderWithProviders(<UploadForm />);
    await user.type(screen.getByLabelText(/Paste PGN/i), '1. e4 e5');
    await user.click(screen.getByRole('button', { name: /Import games/i }));

    expect(
      await screen.findByText(/Provide pasted PGN text or at least one file/),
    ).toBeInTheDocument();
  });

  it('disables submit until there is text or a file', () => {
    renderWithProviders(<UploadForm />);

    expect(screen.getByRole('button', { name: /Import games/i })).toBeDisabled();
  });
});
