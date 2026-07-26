/**
 * Auth API contract.
 *
 * Schemas mirror `backend/app/schemas/auth.py`. MVP login is username-claim, not OAuth
 * (ADR-0014, deferring ADR-0007's Lichess PKCE): the caller picks a platform, types a
 * username, and the backend checks it exists there. Nothing here proves ownership.
 */
import { z } from 'zod';

import { ApiError, apiClient } from '@/shared/lib/api-client';

export const authProviderSchema = z.enum(['lichess', 'chesscom']);
export type AuthProvider = z.infer<typeof authProviderSchema>;

const profileSummarySchema = z.object({
  id: z.string(),
  display_name: z.string(),
  kind: z.string(),
  default_persona: z.string(),
});

export const currentUserSchema = z.object({
  id: z.string(),
  provider: authProviderSchema,
  username: z.string(),
  // False means this login only proved the username exists on the platform, not that the
  // caller owns it — see the module docstring. No UI should present this as a verified
  // identity while it is false.
  verified: z.boolean(),
  profile: profileSummarySchema,
});
export type CurrentUser = z.infer<typeof currentUserSchema>;

/**
 * The signed-in user, or `null` if there is no session.
 *
 * A 401 here means "not logged in", which is an expected, common state — not an error
 * worth surfacing to `useQuery`'s `isError` branch. Any other failure (network down,
 * unexpected 5xx) still propagates.
 */
export async function fetchCurrentUser(signal?: AbortSignal): Promise<CurrentUser | null> {
  try {
    return await apiClient.get('/api/v1/auth/me', currentUserSchema, signal);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      return null;
    }
    throw error;
  }
}

export function login(provider: AuthProvider, username: string): Promise<CurrentUser> {
  return apiClient.post('/api/v1/auth/login', currentUserSchema, { provider, username });
}

export function logout(): Promise<void> {
  return apiClient.post('/api/v1/auth/logout', z.void(), undefined);
}
