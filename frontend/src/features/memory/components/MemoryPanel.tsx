/**
 * Memory audit panel: loads the list, wires deletion (Phase 11). Composition only — see
 * `MemoryList` for the presentation.
 */
import { useDeleteMemory, useMemories } from '../hooks/useMemory';
import { MemoryList } from './MemoryList';

interface MemoryPanelProps {
  /** `undefined` means the caller's own SELF profile (Phase 8b). */
  profileId?: string;
}

export function MemoryPanel({ profileId }: MemoryPanelProps) {
  const { data: memories = [], isLoading, isError } = useMemories(profileId);
  const deleteMemory = useDeleteMemory(profileId);

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }
  if (isError) {
    return <p className="text-sm text-destructive">Could not load your memory.</p>;
  }

  return (
    <MemoryList
      memories={memories}
      onDelete={(memoryId) => deleteMemory.mutate(memoryId)}
      deletingId={deleteMemory.isPending ? deleteMemory.variables : undefined}
    />
  );
}
