/**
 * The memory audit list (Phase 11, ADR-0005): what's remembered, and a way to delete
 * it. Superseded entries are shown, not hidden — the entire point of superseding
 * rather than overwriting is that a wrong memory stays traceable, which means the audit
 * surface has to actually show it, dimmed rather than deleted.
 */
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/lib/utils';

import type { Memory, MemoryKind } from '../api/memory';

const KIND_LABELS: Record<MemoryKind, string> = {
  preference: 'Preference',
  goal: 'Goal',
  recurring_finding: 'Recurring pattern',
};

interface MemoryListProps {
  memories: Memory[];
  onDelete: (memoryId: string) => void;
  deletingId: string | undefined;
}

export function MemoryList({ memories, onDelete, deletingId }: MemoryListProps) {
  if (memories.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Nothing remembered yet — durable preferences and goals you mention in chat will appear here.
      </p>
    );
  }

  return (
    <ul className="space-y-2">
      {memories.map((memory) => {
        const isActive = memory.superseded_at === null;
        return (
          <li
            key={memory.id}
            className={cn(
              'flex items-start justify-between gap-3 rounded-md border border-border px-3 py-2',
              !isActive && 'opacity-50',
            )}
          >
            <div className="space-y-1">
              <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                {KIND_LABELS[memory.kind]}
              </span>
              <p className="text-sm">{memory.content}</p>
              {!isActive && <p className="text-xs text-muted-foreground">No longer active</p>}
            </div>
            {isActive && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => onDelete(memory.id)}
                disabled={deletingId === memory.id}
              >
                {deletingId === memory.id ? 'Removing…' : 'Forget'}
              </Button>
            )}
          </li>
        );
      })}
    </ul>
  );
}
