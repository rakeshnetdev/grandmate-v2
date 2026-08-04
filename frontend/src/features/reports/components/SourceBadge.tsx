/**
 * The provenance badge shown at the top of a generated write-up, with an optional
 * regenerate control beside it.
 *
 * Extracted because `ReportView` and `StoryView` each carried an identical private copy —
 * and the regenerate button would have made that three. `source` is shown, not hidden:
 * "Deterministic summary" for a `fallback` report is not an error state (see
 * `domain/reports/fallback.py`) but it *is* something a reader benefits from knowing.
 *
 * The button is icon-only per the owner's request. That makes the `aria-label` the only
 * name a screen reader has for it, so it is required rather than decorative — and the
 * spinning state doubles as the visible progress indicator, since there is no text to
 * swap to "Regenerating…".
 */
import { RegenerateButton } from '@/shared/components/ui/regenerate-button';

import type { GameReport } from '../api/reports';

interface SourceBadgeProps {
  source: GameReport['source'];
  /** Omitted where regeneration is not offered — the badge then renders alone, exactly as
   * it did before this control existed. */
  onRegenerate?: () => void;
  isRegenerating?: boolean;
  /** Names the thing being regenerated ("report", "story") so two of these on adjacent
   * tabs do not both announce as a bare "Regenerate". */
  label?: string;
}

export function SourceBadge({
  source,
  onRegenerate,
  isRegenerating = false,
  label = 'report',
}: SourceBadgeProps) {
  return (
    <div className="flex shrink-0 items-center gap-1.5">
      <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
        {source === 'fallback' ? 'Deterministic summary' : 'AI-generated'}
      </span>
      {onRegenerate && (
        <RegenerateButton onClick={onRegenerate} label={label} isBusy={isRegenerating} />
      )}
    </div>
  );
}
