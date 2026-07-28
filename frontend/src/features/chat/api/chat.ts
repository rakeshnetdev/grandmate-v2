/**
 * Chat API contract (Phase 10).
 *
 * Schemas mirror `backend/app/schemas/chat.py`.
 */
import { z } from 'zod';

import { apiClient } from '@/shared/lib/api-client';

export const personaSchema = z.enum(['self_learner', 'coach', 'kid']);
export type PersonaValue = z.infer<typeof personaSchema>;

export const chatThreadSchema = z.object({
  id: z.string(),
  profile_id: z.string(),
  title: z.string().nullable(),
  active_game_id: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
});
export type ChatThread = z.infer<typeof chatThreadSchema>;

// A citation's fields vary by `kind` (move / evaluation / variation) — see
// `domain/chat/prompts.py`'s output-contract description. This is a debugging/
// transparency view, not something callers pattern-match on, so it stays loose beyond
// `kind` itself.
const chatCitationSchema = z.object({ kind: z.string() }).passthrough();
export type ChatCitation = z.infer<typeof chatCitationSchema>;

export const chatTurnResponseSchema = z.object({
  thread: chatThreadSchema,
  answer: z.string(),
  citations: z.array(chatCitationSchema),
  grounded: z.boolean(),
});
export type ChatTurnResponse = z.infer<typeof chatTurnResponseSchema>;

const chatMessageSchema = z.object({
  role: z.string(),
  content: z.string(),
});
export type ChatMessage = z.infer<typeof chatMessageSchema>;

export const chatThreadHistorySchema = z.object({
  thread: chatThreadSchema,
  messages: z.array(chatMessageSchema),
});
export type ChatThreadHistory = z.infer<typeof chatThreadHistorySchema>;

function withProfile(path: string, profileId?: string): string {
  return profileId ? `${path}?profile_id=${profileId}` : path;
}

export function listThreads(profileId?: string, signal?: AbortSignal): Promise<ChatThread[]> {
  return apiClient.get(
    withProfile('/api/v1/chat/threads', profileId),
    z.array(chatThreadSchema),
    signal,
  );
}

export function createThread(activeGameId?: string, profileId?: string): Promise<ChatThread> {
  return apiClient.post(withProfile('/api/v1/chat/threads', profileId), chatThreadSchema, {
    active_game_id: activeGameId ?? null,
  });
}

export function getThreadHistory(
  threadId: string,
  profileId?: string,
  signal?: AbortSignal,
): Promise<ChatThreadHistory> {
  return apiClient.get(
    withProfile(`/api/v1/chat/threads/${threadId}`, profileId),
    chatThreadHistorySchema,
    signal,
  );
}

export function sendMessage(
  threadId: string,
  message: string,
  persona: PersonaValue,
  profileId?: string,
): Promise<ChatTurnResponse> {
  return apiClient.post(
    withProfile(`/api/v1/chat/threads/${threadId}/messages`, profileId),
    chatTurnResponseSchema,
    { message, persona },
  );
}
