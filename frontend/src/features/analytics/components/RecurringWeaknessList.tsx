import type { RecurringWeakness } from '../api/analytics';
import { formatPercent, formatWeaknessName } from '../lib/format';

interface RecurringWeaknessListProps {
  weaknesses: RecurringWeakness[];
}

export function RecurringWeaknessList({ weaknesses }: RecurringWeaknessListProps) {
  if (weaknesses.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Nothing recurring often enough yet to call a pattern.
      </p>
    );
  }
  return (
    <ul className="space-y-2">
      {weaknesses.map((w) => (
        <li
          key={`${w.kind}-${w.name}`}
          className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-sm"
        >
          <span>
            {formatWeaknessName(w.name)}{' '}
            <span className="text-xs text-muted-foreground">({w.kind})</span>
          </span>
          <span className="text-muted-foreground">
            {w.games_with_finding} of the window's games ({formatPercent(w.occurrence_rate)})
          </span>
        </li>
      ))}
    </ul>
  );
}
