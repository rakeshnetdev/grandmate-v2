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
