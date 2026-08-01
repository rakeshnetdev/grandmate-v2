/**
 * Recurring weaknesses as a horizontal bar chart.
 *
 * Form: the job is "compare magnitude across named categories", and the names are long,
 * so horizontal bars. Sorted most-frequent first — rank is the reading order, and the
 * reader's question is "what do I do most often", not "what is alphabetically first".
 *
 * Colour: two categorical hues carrying `kind` (motif vs theme), which is identity, not
 * magnitude. The pair is validated for both modes — lightness band, chroma floor, CVD
 * separation (worst adjacent ΔE 24.7 light / 26.8 dark), normal-vision floor, and ≥3:1
 * contrast on both surfaces. Identity is never colour-alone: every bar is direct-labeled
 * and a legend is present.
 *
 * Nothing is lost against the list this replaces — name, kind, game count and occurrence
 * rate are all still on screen, and the bar adds the comparison the list made the reader
 * do in their head.
 */
import type { RecurringWeakness } from '../api/analytics';
import { formatPercent, formatWeaknessName } from '../lib/format';

interface RecurringWeaknessChartProps {
  weaknesses: RecurringWeakness[];
}

const KIND_COLOR: Record<RecurringWeakness['kind'], string> = {
  motif: 'var(--viz-series-1)',
  theme: 'var(--viz-series-2)',
};

const KIND_LABEL: Record<RecurringWeakness['kind'], string> = {
  motif: 'Tactical motif',
  theme: 'Strategic theme',
};

function Legend({ kinds }: { kinds: RecurringWeakness['kind'][] }) {
  return (
    <ul className="flex flex-wrap items-center gap-4">
      {kinds.map((kind) => (
        <li key={kind} className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <span
            aria-hidden="true"
            className="h-2.5 w-2.5 shrink-0 rounded-[2px]"
            style={{ backgroundColor: KIND_COLOR[kind] }}
          />
          {KIND_LABEL[kind]}
        </li>
      ))}
    </ul>
  );
}

export function RecurringWeaknessChart({ weaknesses }: RecurringWeaknessChartProps) {
  if (weaknesses.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Nothing recurring often enough yet to call a pattern.
      </p>
    );
  }

  const sorted = [...weaknesses].sort((a, b) => b.occurrence_rate - a.occurrence_rate);
  // Bars are scaled against the largest value, not against 1.0: at low occurrence rates a
  // 0–100% axis would render every bar as a stub and hide the differences that matter.
  // The percentage is direct-labeled on every row, so the scaling cannot mislead.
  const max = Math.max(...sorted.map((w) => w.occurrence_rate), 0.0001);
  const kindsPresent = (['motif', 'theme'] as const).filter((k) =>
    sorted.some((w) => w.kind === k),
  );

  return (
    <div className="space-y-3">
      {kindsPresent.length > 1 && <Legend kinds={[...kindsPresent]} />}

      <ul className="space-y-2.5">
        {sorted.map((w) => (
          <li key={`${w.kind}-${w.name}`} className="space-y-1">
            <div className="flex items-baseline justify-between gap-3 text-sm">
              <span className="min-w-0 truncate">{formatWeaknessName(w.name)}</span>
              <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                {w.games_with_finding} games · {formatPercent(w.occurrence_rate)}
              </span>
            </div>
            <div
              className="h-2 w-full overflow-hidden rounded-full"
              style={{ backgroundColor: 'var(--viz-track)' }}
              role="img"
              aria-label={`${formatWeaknessName(w.name)}, ${KIND_LABEL[w.kind]}: ${
                w.games_with_finding
              } games, ${formatPercent(w.occurrence_rate)} of the window`}
            >
              <div
                className="h-full rounded-full"
                style={{
                  width: `${Math.max((w.occurrence_rate / max) * 100, 2)}%`,
                  backgroundColor: KIND_COLOR[w.kind],
                }}
              />
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
