/**
 * UserMenu tests: logged-out and logged-in states, both driven only by mocking `fetch`
 * for the `/auth/me` call `useCurrentUser` makes on mount.
 */
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { renderWithProviders } from '@/test/render';

import { UserMenu } from './UserMenu';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('UserMenu', () => {
  it('shows a login link when there is no session', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: false, status: 401, json: () => Promise.resolve({}) }),
    );

    renderWithProviders(<UserMenu />);

    expect(await screen.findByRole('link', { name: /Log in/i })).toBeInTheDocument();
  });

  it('shows the username and a logout button when a session exists', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve({
            id: 'u1',
            provider: 'lichess',
            username: 'magnus',
            verified: false,
            profile: {
              id: 'p1',
              display_name: 'magnus',
              kind: 'self',
              default_persona: 'self_learner',
            },
          }),
      }),
    );

    renderWithProviders(<UserMenu />);

    expect(await screen.findByText('magnus')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Log out/i })).toBeInTheDocument();
  });

  it('clicking log out calls the logout endpoint', async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (typeof url === 'string' && url.includes('/auth/logout')) {
        return Promise.resolve({
          ok: true,
          status: 204,
          json: () => Promise.reject(new Error('no body')),
        });
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve({
            id: 'u1',
            provider: 'lichess',
            username: 'magnus',
            verified: false,
            profile: {
              id: 'p1',
              display_name: 'magnus',
              kind: 'self',
              default_persona: 'self_learner',
            },
          }),
      });
    });
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();

    renderWithProviders(<UserMenu />);
    await screen.findByText('magnus');
    await user.click(screen.getByRole('button', { name: /Log out/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/auth/logout'),
        expect.objectContaining({ method: 'POST' }),
      );
    });
  });
});
