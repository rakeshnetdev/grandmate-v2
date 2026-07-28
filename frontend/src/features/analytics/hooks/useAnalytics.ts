/**
 * Feature hook for the profile analytics dashboard (Phase 8).
 *
 * `profileId` (Phase 8b) is threaded into the query key so switching between "My games"
 * and "Study games" never shows the other profile's cached snapshot.
 */
import { useQuery } from '@tanstack/react-query';

import { fetchProfileAnalytics } from '../api/analytics';

const SELF_KEY = 'self';

export const analyticsKeys = {
  all: ['analytics'] as const,
  profile: (windowSize: number, profileId: string | undefined) =>
    [...analyticsKeys.all, 'profile', profileId ?? SELF_KEY, windowSize] as const,
};

export function useProfileAnalytics(
  windowSize: number,
  profileId?: string,
  options: { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: analyticsKeys.profile(windowSize, profileId),
    queryFn: ({ signal }) => fetchProfileAnalytics(windowSize, profileId, signal),
    enabled: options.enabled ?? true,
  });
}
