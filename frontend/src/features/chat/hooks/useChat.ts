/**
 * Feature hooks for chat threads (Phase 10).
 *
 * Single-shot request/response per message (no streaming) — a turn resolves only after
 * the backend's tool-calling loop and grounding guardrail finish, same trade-off Phase
 * 9's report generation already made for the same reason: simpler transport, and the
 * guardrail can reject/regenerate before anything reaches the UI.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  createThread,
  getThreadHistory,
  listThreads,
  sendMessage,
  type PersonaValue,
} from '../api/chat';

const SELF_KEY = 'self';

export const chatKeys = {
  all: ['chat'] as const,
  threads: (profileId: string | undefined) =>
    [...chatKeys.all, profileId ?? SELF_KEY, 'threads'] as const,
  thread: (threadId: string, profileId: string | undefined) =>
    [...chatKeys.all, profileId ?? SELF_KEY, 'thread', threadId] as const,
};

export function useThreads(profileId?: string) {
  return useQuery({
    queryKey: chatKeys.threads(profileId),
    queryFn: ({ signal }) => listThreads(profileId, signal),
  });
}

export function useCreateThread(profileId?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (activeGameId?: string) => createThread(activeGameId, profileId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: chatKeys.threads(profileId) });
    },
  });
}

export function useThreadHistory(threadId: string | undefined, profileId?: string) {
  return useQuery({
    queryKey: chatKeys.thread(threadId ?? '', profileId),
    queryFn: ({ signal }) => getThreadHistory(threadId as string, profileId, signal),
    enabled: Boolean(threadId),
  });
}

export function useSendMessage(threadId: string, profileId?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ message, persona }: { message: string; persona: PersonaValue }) =>
      sendMessage(threadId, message, persona, profileId),
    onSuccess: () => {
      // Re-fetch rather than optimistically append: the checkpointer is the source of
      // truth for a thread's transcript, and re-reading it after a turn is cheap and
      // avoids the UI's local copy ever silently diverging from what the backend stored.
      queryClient.invalidateQueries({ queryKey: chatKeys.thread(threadId, profileId) });
      queryClient.invalidateQueries({ queryKey: chatKeys.threads(profileId) });
    },
  });
}
