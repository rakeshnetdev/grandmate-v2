/**
 * Shown while a game's engine analysis is still running, in place of an error.
 *
 * The panel polls behind this, so it replaces itself the moment the report exists — the
 * reader never has to work out that a refresh would help.
 */
import { Loader2 } from 'lucide-react';

import { analyzingLineFor } from '../lib/pending';

interface AnalyzingNoticeProps {
  /** Seeds the line choice so it stays stable for this game across re-renders. */
  gameId: string;
}

export function AnalyzingNotice({ gameId }: AnalyzingNoticeProps) {
  return (
    <div className="flex items-start gap-2.5 text-sm">
      <Loader2
        className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-muted-foreground"
        aria-hidden="true"
      />
      <div role="status" aria-live="polite">
        <p className="font-medium">{analyzingLineFor(gameId)}</p>
        <p className="mt-0.5 text-xs text-muted-foreground">
          This page updates itself when the analysis lands — nothing to refresh.
        </p>
      </div>
    </div>
  );
}
