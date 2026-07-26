/**
 * LoginForm tests: the whole chain from form input to API call to success/error UI, with
 * only `fetch` mocked.
 */
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { renderWithProviders } from '@/test/render';

import { LoginForm } from './LoginForm';

function mockFetchOnce(body: unknown, ok = true, status = ok ? 200 : 404) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok,
      status,
      json: () => Promise.resolve(body),
    }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

const validUser = {
  id: 'u1',
  provider: 'lichess',
  username: 'magnus',
  verified: false,
  profile: { id: 'p1', display_name: 'magnus', kind: 'self', default_persona: 'self_learner' },
};

describe('LoginForm', () => {
  it('defaults to Lichess and submits the typed username', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(validUser),
    });
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();

    renderWithProviders(<LoginForm />);
    await user.type(screen.getByLabelText(/Lichess username/i), 'magnus');
    await user.click(screen.getByRole('button', { name: /Continue with Lichess/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/auth/login'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ provider: 'lichess', username: 'magnus' }),
        }),
      );
    });
  });

  it('switches the platform and label when Chess.com is picked', async () => {
    const user = userEvent.setup();
    renderWithProviders(<LoginForm />);

    await user.click(screen.getByRole('radio', { name: 'Chess.com' }));

    expect(screen.getByLabelText(/Chess\.com username/i)).toBeInTheDocument();
  });

  it('calls onSuccess once login resolves', async () => {
    mockFetchOnce(validUser);
    const onSuccess = vi.fn();
    const user = userEvent.setup();

    renderWithProviders(<LoginForm onSuccess={onSuccess} />);
    await user.type(screen.getByLabelText(/Lichess username/i), 'magnus');
    await user.click(screen.getByRole('button', { name: /Continue with Lichess/i }));

    await waitFor(() => expect(onSuccess).toHaveBeenCalled());
  });

  it('shows a not-found message on a 404', async () => {
    mockFetchOnce({ detail: 'nope' }, false, 404);
    const user = userEvent.setup();

    renderWithProviders(<LoginForm />);
    await user.type(screen.getByLabelText(/Lichess username/i), 'nobody');
    await user.click(screen.getByRole('button', { name: /Continue with Lichess/i }));

    expect(await screen.findByText(/No Lichess account named "nobody"/)).toBeInTheDocument();
  });

  it('disables the submit button while the username is blank', () => {
    renderWithProviders(<LoginForm />);

    expect(screen.getByRole('button', { name: /Continue with Lichess/i })).toBeDisabled();
  });
});
