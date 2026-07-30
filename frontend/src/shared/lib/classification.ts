/**
 * Move-classification labels and colors, shared between the single-game analysis view
 * and the profile analytics dashboard so the same five-way scale (best/good/inaccuracy/
 * mistake/blunder) reads identically wherever it appears.
 */

export type MoveClassificationKey = 'best' | 'good' | 'inaccuracy' | 'mistake' | 'blunder';

export const CLASSIFICATION_ORDER: MoveClassificationKey[] = [
  'best',
  'good',
  'inaccuracy',
  'mistake',
  'blunder',
];

export const CLASSIFICATION_LABEL: Record<MoveClassificationKey, string> = {
  best: 'Best',
  good: 'Good',
  inaccuracy: 'Inaccuracy',
  mistake: 'Mistake',
  blunder: 'Blunder',
};

export const CLASSIFICATION_CLASS: Record<MoveClassificationKey, string> = {
  best: 'text-green-600 dark:text-green-500',
  good: 'text-emerald-600 dark:text-emerald-500',
  inaccuracy: 'text-yellow-600 dark:text-yellow-500',
  mistake: 'text-orange-600 dark:text-orange-500',
  blunder: 'text-destructive',
};

/**
 * Pill-badge palette (Phase 16a, D-035) — inspired by, not copied from, the sibling
 * `grandmate/` frontend's severity badges: 10%-opacity background, full-opacity text,
 * 20%-opacity border, one consistent formula across every severity/classification
 * surface (move lists, `ClassificationBadge`, and the chess-notation prose highlighter
 * in `shared/lib/prose.tsx`) rather than the ad-hoc plain-text coloring `CLASSIFICATION_
 * CLASS` above still uses for dense table rows, where a pill would be visual noise.
 */
export const CLASSIFICATION_BADGE_CLASS: Record<MoveClassificationKey, string> = {
  best: 'bg-green-500/10 text-green-700 border-green-500/20 dark:text-green-400',
  good: 'bg-emerald-500/10 text-emerald-700 border-emerald-500/20 dark:text-emerald-400',
  inaccuracy: 'bg-yellow-500/10 text-yellow-700 border-yellow-500/20 dark:text-yellow-400',
  mistake: 'bg-orange-500/10 text-orange-700 border-orange-500/20 dark:text-orange-400',
  blunder: 'bg-red-500/10 text-red-700 border-red-500/20 dark:text-red-400',
};
