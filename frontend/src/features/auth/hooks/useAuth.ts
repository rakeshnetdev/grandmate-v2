/**
 * Feature hooks for authentication.
 *
 * `useCurrentUser` is the single source of truth for "who is logged in" — components
 * read it rather than tracking their own local auth state, so login and logout
 * everywhere else just invalidate this one query key.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type { AuthProvider } from '../api/auth';
import { fetchCurrentUser, login, logout } from '../api/auth';

export const authKeys = {
  all: ['auth'] as const,
  currentUser: () => [...authKeys.all, 'current-user'] as const,
};

export function useCurrentUser() {
  return useQuery({
    queryKey: authKeys.currentUser(),
    queryFn: ({ signal }) => fetchCurrentUser(signal),
    // A session lasts a week server-side; there is no need to recheck every few seconds.
    staleTime: 60_000,
  });
}

export function useLogin() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ provider, username }: { provider: AuthProvider; username: string }) =>
      login(provider, username),
    onSuccess: (user) => {
      queryClient.setQueryData(authKeys.currentUser(), user);
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: logout,
    onSuccess: () => {
      queryClient.setQueryData(authKeys.currentUser(), null);
    },
  });
}
