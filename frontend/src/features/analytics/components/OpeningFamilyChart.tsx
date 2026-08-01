/**
 * Opening family performance as a chart, without dropping a column.
 *
 * The table this replaces carried five things per family: games, W-D-L, win rate, and
 * average accuracy. Two of those are different measures on different scales, so they get
 * two aligned figures sharing one set of row labels — never one chart with two y-axes,
 * which is the single most misread thing in charting.
 *
 * Left figure: **result mix** as a proportional stacked bar, wins → draws → losses. Bar
 * width is the share of that family's games, so the segment lengths *are* the win/draw/
 * loss rate; the counts ride along in the label and the accessible description. Colour is
 * the validated diverging pair (blue good ↔ red bad) with an achromatic neutral for
 * draws, because the reader's question is polarity, not identity.
 *
 * Right figure: **average accuracy** as a one-hue sequential meter on a fixed 0–100
 * scale. Fixed rather than relative: accuracy is already a percentage with an absolute
 * meaning, and rescaling it to the local max would make a weak set of games look strong.
 *
 * A 2px surface-coloured gap separates adjacent stack segments so they read as distinct
 * marks rather than one continuous bar.
 */
import type { OpeningFamilyPerformance } from '../api/analytics';
import { formatPercent, formatPoints } from '../lib/format';

interface OpeningFamilyChartProps {
  families: OpeningFamilyPerformance[];
}

const RESULT_SEGMENTS = [
  { key: 'wins' as const, label: 'Wins', color: 'var(--viz-win)' },
  { key: 'draws' as const, label: 'Draws', color: 'var(--viz-draw)' },
  { key: 'losses' as const, label: 'Losses', color: 'var(--viz-loss)' },
];

function Legend() {
  return (
    <ul className="flex flex-wrap items-center gap-4">
      {RESULT_SEGMENTS.map((segment) => (
        <li key={segment.key} className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <span
            aria-hidden="true"
            className="h-2.5 w-2.5 shrink-0 rounded-[2px]"
            style={{ backgroundColor: segment.color }}
          />
          {segment.label}
        </li>
      ))}
    </ul>
  );
}

function ResultBar({ family }: { family: OpeningFamilyPerformance }) {
  // Guard against a zero-game row producing NaN widths.
  const total = Math.max(family.games, 1);

  return (
    <div
      className="flex h-2.5 w-full overflow-hidden rounded-full"
      style={{ backgroundColor: 'var(--viz-track)' }}
      role="img"
      aria-label={`${family.family}: ${family.wins} wins, ${family.draws} draws, ${family.losses} losses of ${family.games} games`}
    >
      {RESULT_SEGMENTS.map((segment) => {
        const count = family[segment.key];
        if (count === 0) return null;
        return (
          <span
            key={segment.key}
            title={`${segment.label}: ${count}`}
            className="h-full first:rounded-l-full last:rounded-r-full"
            style={{
              width: `${(count / total) * 100}%`,
              backgroundColor: segment.color,
              // 2px of surface between adjacent segments so they read as separate marks.
              boxShadow: '2px 0 0 0 var(--card)',
            }}
          />
        );
      })}
    </div>
  );
}

function AccuracyMeter({ value }: { value: number | null }) {
  if (value === null) {
    return <span className="text-xs text-muted-foreground">—</span>;
  }
  return (
    <div className="flex items-center gap-2">
      <div
        className="h-1.5 w-full overflow-hidden rounded-full"
        style={{ backgroundColor: 'var(--viz-track)' }}
        role="img"
        aria-label={`Average accuracy ${formatPoints(value)}%`}
      >
        <div
          className="h-full rounded-full"
          style={{
            // Fixed 0–100 scale: accuracy means the same thing everywhere.
            width: `${Math.min(Math.max(value, 0), 100)}%`,
            backgroundColor: 'var(--viz-series-1)',
          }}
        />
      </div>
      <span className="w-11 shrink-0 text-right text-xs tabular-nums text-muted-foreground">
        {formatPoints(value)}%
      </span>
    </div>
  );
}

export function OpeningFamilyChart({ families }: OpeningFamilyChartProps) {
  if (families.length === 0) {
    return <p className="text-sm text-muted-foreground">No openings identified in this window.</p>;
  }

  // Most-played first: how often you reach a family is the context for everything else
  // in the row.
  const sorted = [...families].sort((a, b) => b.games - a.games);

  return (
    <div className="space-y-3">
      <Legend />

      <ul className="space-y-3">
        {sorted.map((f) => (
          <li key={f.family} className="space-y-1.5">
            <div className="flex items-baseline justify-between gap-3 text-sm">
              <span className="min-w-0 truncate">{f.family}</span>
              <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                {f.games} games · {f.wins}-{f.draws}-{f.losses} · {formatPercent(f.win_rate)} win
              </span>
            </div>

            <div className="grid items-center gap-x-4 gap-y-1.5 sm:grid-cols-[1fr_11rem]">
              <ResultBar family={f} />
              <AccuracyMeter value={f.average_accuracy} />
            </div>
          </li>
        ))}
      </ul>

      <p className="text-xs text-muted-foreground">
        Bar shows result mix across that family&apos;s games. The right-hand meter is average
        accuracy on a fixed 0–100 scale.
      </p>
    </div>
  );
}
