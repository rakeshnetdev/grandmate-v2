/**
 * The workspace's "PGN" tab (Phase 16b follow-up): the game's raw PGN exactly as
 * imported, read-only but selectable, with a one-click copy button. A `<textarea>`
 * rather than a `<pre>` so text selection, scrolling, and copying behave like users
 * expect from "the box with my PGN in it".
 */
import { useEffect, useState } from 'react';

import { useGamePgn } from '@/features/games';
import { Button } from '@/shared/components/ui/button';

interface PgnTabProps {
  gameId: string;
  profileId?: string;
}

export function PgnTab({ gameId, profileId }: PgnTabProps) {
  const { data: pgn, isLoading, isError } = useGamePgn(gameId, profileId);
  const [copied, setCopied] = useState(false);

  // "Copied" is transient feedback, not state worth keeping — reset it after a moment
  // and whenever the selected game changes.
  useEffect(() => {
    setCopied(false);
  }, [gameId]);
  useEffect(() => {
    if (!copied) {
      return;
    }
    const timer = setTimeout(() => setCopied(false), 2000);
    return () => clearTimeout(timer);
  }, [copied]);

  if (isError) {
    return <p className="text-sm text-destructive">Could not load this game's PGN.</p>;
  }
  if (isLoading || pgn === undefined) {
    return <p className="text-sm text-muted-foreground">Loading PGN…</p>;
  }

  async function handleCopy() {
    await navigator.clipboard.writeText(pgn ?? '');
    setCopied(true);
  }

  return (
    <div className="flex h-full flex-col gap-2">
      <div className="flex items-center justify-end">
        <Button type="button" variant="outline" size="sm" onClick={handleCopy}>
          {copied ? 'Copied!' : 'Copy PGN'}
        </Button>
      </div>
      <textarea
        readOnly
        value={pgn}
        aria-label="Game PGN"
        spellCheck={false}
        className="min-h-64 flex-1 resize-none rounded-md border border-border bg-muted/30 p-3 font-mono text-xs leading-relaxed focus:outline-none"
      />
    </div>
  );
}
