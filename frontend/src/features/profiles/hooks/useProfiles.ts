/**
 * Feature hook for the caller's own profiles (Phase 8b): SELF plus the study profile
 * every account gets at login.
 */
import { useQuery } from '@tanstack/react-query';

import { fetchProfiles } from '../api/profiles';

export const profileKeys = {
  all: ['profiles'] as const,
  list: () => [...profileKeys.all, 'list'] as const,
};

export function useProfiles(options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: profileKeys.list(),
    queryFn: ({ signal }) => fetchProfiles(signal),
    enabled: options.enabled ?? true,
  });
}
