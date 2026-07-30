/**
 * Pill badge for a move classification (Phase 16a, D-035) — see `shared/lib/
 * classification.ts`'s `CLASSIFICATION_BADGE_CLASS` for the color formula this applies.
 */
import {
  CLASSIFICATION_BADGE_CLASS,
  CLASSIFICATION_LABEL,
  type MoveClassificationKey,
} from '@/shared/lib/classification';
import { cn } from '@/shared/lib/utils';

interface ClassificationBadgeProps {
  classification: MoveClassificationKey;
  className?: string;
}

export function ClassificationBadge({ classification, className }: ClassificationBadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-bold tracking-wider uppercase',
        CLASSIFICATION_BADGE_CLASS[classification],
        className,
      )}
    >
      {CLASSIFICATION_LABEL[classification]}
    </span>
  );
}
