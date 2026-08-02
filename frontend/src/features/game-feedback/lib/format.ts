/** Display formatting for pattern feedback (Phase 19). */

import type { Band, MetricComparison } from '../api/patternFeedback';

/** How a band reads to the player. Deliberately comparative, never absolute — the point
 * of this feature is "against your usual", so no phrase here works without that frame. */
export const BAND_LABELS: Record<Band, string> = {
  well_above: 'Well above your usual',
  above: 'Above your usual',
  in_line: 'In line with your usual',
  below: 'Below your usual',
  well_below: 'Well below your usual',
};

/** Muted tints, matching the restraint of the story and learning surfaces: a below-par
 * game is information, not an alarm. */
export const BAND_TONES: Record<Band, string> = {
  well_above: 'text-emerald-600 dark:text-emerald-400',
  above: 'text-emerald-600/80 dark:text-emerald-400/80',
  in_line: 'text-muted-foreground',
  below: 'text-amber-600/80 dark:text-amber-400/80',
  well_below: 'text-amber-600 dark:text-amber-400',
};

const METRIC_LABELS: Record<MetricComparison['name'], string> = {
  accuracy: 'Your accuracy',
  blunder_rate: 'Your blunder rate',
  critical_moments: 'Critical moments',
};

export function metricLabel(name: MetricComparison['name']): string {
  return METRIC_LABELS[name];
}

/** Metrics carry different units, so each formats on its own terms rather than through
 * one generic number formatter that would print "0.0435 blunder rate". */
export function metricValue(name: MetricComparison['name'], value: number): string {
  if (name === 'accuracy') {
    return `${value.toFixed(1)}%`;
  }
  if (name === 'blunder_rate') {
    return `${(value * 100).toFixed(1)}%`;
  }
  return value.toFixed(0);
}

/** `hanging_piece` -> `Hanging piece`. Same treatment the analytics dashboard gives a
 * weakness name, so one habit reads identically wherever the player meets it. */
export function weaknessLabel(name: string): string {
  const spaced = name.replace(/_/g, ' ');
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

/** "6 of your last 20 games". */
export function occurrenceText(withFinding: number, baselineGames: number): string {
  return `${withFinding} of your last ${baselineGames} games`;
}

/** How many move numbers to name before summarising the rest. A recurring habit can fire
 * ten times in one game (seen on real data), and a ten-number list stops being readable
 * long before it stops being accurate. */
const MAX_MOVES_SHOWN = 4;

/** "move 3, 9, 10, 12 +6 more" — never a bare truncation, so the count stays honest. */
export function moveNumbersText(moveNumbers: number[]): string {
  if (moveNumbers.length === 0) {
    return '';
  }
  const shown = moveNumbers.slice(0, MAX_MOVES_SHOWN).join(', ');
  const remaining = moveNumbers.length - MAX_MOVES_SHOWN;
  return remaining > 0 ? `move ${shown} +${remaining} more` : `move ${shown}`;
}
