/**
 * Chat page (Phase 10). `profile` follows the same self/study-profile URL convention as
 * `DashboardPage`/`GamesPage` (Phase 8b); `game` pre-seeds a new thread's context when
 * arriving from a game detail page's "Ask about this game" link. `thread` keeps the
 * open conversation in the URL so a reload restores it — the checkpointer already
 * persists the thread itself; without this, refreshing the page would strand a real,
 * durable conversation behind a "select a conversation" screen for no reason.
 */
import { useSearchParams } from 'react-router-dom';

import { ChatPanel } from '@/features/chat';

export function ChatPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const profileId = searchParams.get('profile') ?? undefined;
  const gameId = searchParams.get('game') ?? undefined;
  const threadId = searchParams.get('thread') ?? undefined;

  function handleSelectThread(nextThreadId: string | undefined) {
    setSearchParams((params) => {
      const next = new URLSearchParams(params);
      if (nextThreadId) {
        next.set('thread', nextThreadId);
      } else {
        next.delete('thread');
      }
      return next;
    });
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Chat</h1>
        <p className="mt-1 text-muted-foreground">
          Ask about your games, openings, tactics, or strategy.
        </p>
      </div>

      <ChatPanel
        profileId={profileId}
        activeGameId={gameId}
        selectedThreadId={threadId}
        onSelectThread={handleSelectThread}
      />
    </div>
  );
}
