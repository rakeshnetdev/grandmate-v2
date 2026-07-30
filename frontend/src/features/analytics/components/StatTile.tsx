/**
 * Value + delta stat tile — no sparkline, since a snapshot only has "this window" and
 * "the window before it," not a real time series (see the dataviz skill's stat-tile
 * contract: sparkline is optional and there's nothing meaningful to draw from two
 * points). Delta color follows direction *and* whether up is good for this particular
 * metric — a rising blunder rate is bad news in green's opposite, not green.
 */
import { cn } from '@/shared/lib/utils';

interface StatTileProps {
  label: string;
  value: string;
  delta: number | null;
  /** Formats the delta's magnitude, e.g. `(d) => `${d.toFixed(1)} pts`` */
  formatDelta: (delta: number) => string;
  higherIsBetter: boolean;
  /** Plain-language one-liner on what this number measures — bare metric labels like
   * "Accuracy" mean nothing to a reader without it. */
  description?: string;
}

export function StatTile({
  label,
  value,
  delta,
  formatDelta,
  higherIsBetter,
  description,
}: StatTileProps) {
  const isGood = delta === null ? null : higherIsBetter ? delta > 0 : delta < 0;
  const deltaColor =
    delta === null || delta === 0
      ? 'text-muted-foreground'
      : isGood
        ? 'text-green-600 dark:text-green-500'
        : 'text-destructive';
  const arrow = delta === null || delta === 0 ? '' : delta > 0 ? '▲ ' : '▼ ';

  return (
    <div className="rounded-md border border-border p-4">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-semibold tracking-tight">{value}</p>
      <p className={cn('mt-1 text-xs', deltaColor)}>
        {delta === null
          ? 'not enough prior data'
          : `${arrow}${formatDelta(delta)} vs. prior window`}
      </p>
      {description && <p className="mt-2 text-xs text-muted-foreground">{description}</p>}
    </div>
  );
}
