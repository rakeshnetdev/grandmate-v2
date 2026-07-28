/**
 * Thread list + new-chat entry point (Phase 10).
 */
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/lib/utils';

import type { ChatThread } from '../api/chat';

interface ThreadListProps {
  threads: ChatThread[];
  selectedThreadId: string | undefined;
  onSelect: (threadId: string) => void;
  onCreate: () => void;
  creating: boolean;
}

export function ThreadList({
  threads,
  selectedThreadId,
  onSelect,
  onCreate,
  creating,
}: ThreadListProps) {
  return (
    <div className="flex flex-col gap-2">
      <Button type="button" size="sm" onClick={onCreate} disabled={creating}>
        {creating ? 'Starting…' : 'New chat'}
      </Button>

      {threads.length === 0 ? (
        <p className="text-sm text-muted-foreground">No conversations yet.</p>
      ) : (
        <ul className="space-y-1">
          {threads.map((thread) => (
            <li key={thread.id}>
              <button
                type="button"
                onClick={() => onSelect(thread.id)}
                className={cn(
                  'w-full truncate rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted',
                  thread.id === selectedThreadId && 'bg-muted font-medium',
                )}
              >
                {thread.title ?? 'New conversation'}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
