/**
 * Thread list + composer + transcript (Phase 10). Composition only — see `ThreadList`,
 * `ChatMessageList`, `ChatComposer` for the pieces.
 */
import { useState } from 'react';

import { PersonaSwitcher, type PersonaValue } from '@/features/reports';
import { Card, CardContent } from '@/shared/components/ui/card';

import { useCreateThread, useSendMessage, useThreadHistory, useThreads } from '../hooks/useChat';
import { ChatComposer } from './ChatComposer';
import { ChatMessageList } from './ChatMessageList';
import { ThreadList } from './ThreadList';

interface ChatPanelProps {
  /** `undefined` means the caller's own SELF profile (Phase 8b). */
  profileId?: string;
  /** Pre-seeds a new thread's context — set when opened from a game detail page. */
  activeGameId?: string;
  /**
   * Controlled selection, so a page can keep it in the URL and survive a reload (the
   * checkpointer already persists the thread itself — losing which one was open on
   * refresh would be a pure UI regression on top of real, durable data). Falls back to
   * internal state when the caller does not need that, e.g. in isolation in tests.
   */
  selectedThreadId?: string;
  onSelectThread?: (threadId: string | undefined) => void;
}

export function ChatPanel({
  profileId,
  activeGameId,
  selectedThreadId: controlledThreadId,
  onSelectThread,
}: ChatPanelProps) {
  const [internalThreadId, setInternalThreadId] = useState<string>();
  const selectedThreadId = controlledThreadId ?? internalThreadId;
  const setSelectedThreadId = onSelectThread ?? setInternalThreadId;
  const [persona, setPersona] = useState<PersonaValue>('self_learner');

  const { data: threads = [] } = useThreads(profileId);
  const createThread = useCreateThread(profileId);
  const { data: history } = useThreadHistory(selectedThreadId, profileId);
  const sendMessage = useSendMessage(selectedThreadId ?? '', profileId);

  const handleCreate = () => {
    createThread.mutate(activeGameId, {
      onSuccess: (thread) => setSelectedThreadId(thread.id),
    });
  };

  const handleSend = (message: string) => {
    if (selectedThreadId) {
      sendMessage.mutate({ message, persona });
    }
  };

  return (
    // Stacked, not a side-by-side grid (Phase 16a): this panel's primary home is now a
    // narrow docked side panel (`workspace/components/ChatDock.tsx`), where a
    // viewport-width `md:` breakpoint would still trigger a cramped two-column layout
    // regardless of how narrow the panel itself actually is.
    <div className="flex h-full flex-col gap-3">
      <Card className="max-h-32 shrink-0 overflow-y-auto">
        <CardContent className="pt-4">
          <ThreadList
            threads={threads}
            selectedThreadId={selectedThreadId}
            onSelect={setSelectedThreadId}
            onCreate={handleCreate}
            creating={createThread.isPending}
          />
        </CardContent>
      </Card>

      <Card className="flex flex-1 flex-col overflow-hidden">
        <CardContent className="flex flex-1 flex-col gap-4 overflow-hidden pt-4">
          {selectedThreadId ? (
            <>
              <PersonaSwitcher value={persona} onChange={setPersona} />
              <div className="flex-1 overflow-y-auto">
                <ChatMessageList
                  messages={history?.messages ?? []}
                  pending={sendMessage.isPending}
                />
              </div>
              <ChatComposer onSend={handleSend} disabled={sendMessage.isPending} />
            </>
          ) : (
            <p className="text-sm text-muted-foreground">
              Select a conversation or start a new one.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
