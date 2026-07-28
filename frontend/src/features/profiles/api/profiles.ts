/**
 * Profile listing API contract (Phase 8b).
 *
 * Schema mirrors `backend/app/schemas/profiles.py`.
 */
import { z } from 'zod';

import { apiClient } from '@/shared/lib/api-client';

export const profileSummarySchema = z.object({
  id: z.string(),
  kind: z.enum(['self', 'child', 'student', 'opponent', 'shared']),
  display_name: z.string(),
});
export type ProfileSummary = z.infer<typeof profileSummarySchema>;

const profileListSchema = z.array(profileSummarySchema);

export function fetchProfiles(signal?: AbortSignal): Promise<ProfileSummary[]> {
  return apiClient.get('/api/v1/profiles', profileListSchema, signal);
}
