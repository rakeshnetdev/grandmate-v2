/**
 * Picks the week's focus items from profile analytics.
 *
 * Deterministic selection over already-computed aggregates — no LLM, no new API call.
 * This is presentation-layer prioritisation of backend truth, not new analysis: the
 * numbers it sorts on (`win_rate`, `occurrence_rate`) are exactly what
 * `domain/analytics/metrics.py` produced.
 */
import type {
  OpeningFamilyPerformance,
  ProfileAnalytics,
  RecurringWeakness,
} from '@/features/analytics';

/** How many of each kind the week's focus shows. Three is a week's worth, not a backlog. */
export const FOCUS_COUNT = 3;

/**
 * A family seen only once is noise — one loss in one game says nothing about the
 * opening. Two is still a small sample, which is why the panel labels these as
 * suggestions rather than conclusions.
 */
const MIN_GAMES_FOR_OPENING_FOCUS = 2;

/**
 * Full ranked list, weakest openings first: lowest win rate, breaking ties on lower accuracy.
 *
 * A `null` win_rate means the metric could not be computed for that family; those sort
 * last rather than being treated as zero, which would promote them above genuinely bad
 * results.
 */
export function rankOpeningsToLearn(
  analytics: ProfileAnalytics | undefined,
): OpeningFamilyPerformance[] {
  if (!analytics) return [];

  return [...analytics.opening_family_performance]
    .filter((o) => o.games >= MIN_GAMES_FOR_OPENING_FOCUS)
    .sort((a, b) => {
      if (a.win_rate === null && b.win_rate === null) return 0;
      if (a.win_rate === null) return 1;
      if (b.win_rate === null) return -1;
      if (a.win_rate !== b.win_rate) return a.win_rate - b.win_rate;
      return (a.average_accuracy ?? 0) - (b.average_accuracy ?? 0);
    });
}

/**
 * Full ranked list, most frequent tactical motifs first.
 *
 * Filtered to `motif` and not `theme`: motifs map onto Lichess puzzle themes, so they
 * are directly practisable. Strategic themes (bad bishop, space advantage) have no
 * puzzle equivalent and belong in the written training plan instead.
 */
export function rankMotifsToLearn(analytics: ProfileAnalytics | undefined): RecurringWeakness[] {
  if (!analytics) return [];

  return analytics.recurring_weaknesses
    .filter((w) => w.kind === 'motif')
    .sort((a, b) => b.occurrence_rate - a.occurrence_rate);
}

/**
 * Split a ranked list into what to show now and what has already been covered.
 *
 * Driven by a set of covered keys rather than a round index, so the split stays correct
 * when the ranking is recomputed — new games change the order, and a positional cursor
 * would start describing items the reader never saw.
 *
 * "Covered" means shown and moved past, not verified as solved. There is no completion
 * signal from Lichess to check against, and inventing one would be a claim the system
 * cannot support.
 */
export function splitFocus<T>(
  ranked: T[],
  keyOf: (item: T) => string,
  covered: ReadonlySet<string>,
): { current: T[]; completed: T[] } {
  const remaining: T[] = [];
  const completed: T[] = [];
  for (const item of ranked) {
    (covered.has(keyOf(item)) ? completed : remaining).push(item);
  }
  return { current: remaining.slice(0, FOCUS_COUNT), completed };
}
