/**
 * Long-term memory audit API contract (Phase 11).
 *
 * Schema mirrors `backend/app/schemas/memory.py`.
 */
import { z } from 'zod';

import { apiClient } from '@/shared/lib/api-client';

export const memoryKindSchema = z.enum(['preference', 'goal', 'recurring_finding']);
export type MemoryKind = z.infer<typeof memoryKindSchema>;

export const memorySchema = z.object({
  id: z.string(),
  kind: memoryKindSchema,
  content: z.string(),
  confidence: z.number(),
  source_thread_id: z.string().nullable(),
  created_at: z.string(),
  // `null` means active — see `MemoryOut`'s own docstring for why there is no separate
  // boolean flag.
  superseded_at: z.string().nullable(),
});
export type Memory = z.infer<typeof memorySchema>;

function withProfile(path: string, profileId?: string): string {
  return profileId ? `${path}?profile_id=${profileId}` : path;
}

export function listMemories(profileId?: string, signal?: AbortSignal): Promise<Memory[]> {
  return apiClient.get(withProfile('/api/v1/memory', profileId), z.array(memorySchema), signal);
}

export function deleteMemory(memoryId: string, profileId?: string): Promise<void> {
  return apiClient.delete(withProfile(`/api/v1/memory/${memoryId}`, profileId));
}
