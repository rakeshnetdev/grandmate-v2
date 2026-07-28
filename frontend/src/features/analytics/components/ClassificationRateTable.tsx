import {
  CLASSIFICATION_CLASS,
  CLASSIFICATION_LABEL,
  CLASSIFICATION_ORDER,
} from '@/shared/lib/classification';
import { cn } from '@/shared/lib/utils';

import type { ProfileAnalytics } from '../api/analytics';
import { formatPercent } from '../lib/format';

interface ClassificationRateTableProps {
  analytics: ProfileAnalytics;
}

export function ClassificationRateTable({ analytics }: ClassificationRateTableProps) {
  const { current, delta } = analytics.classification_rates;
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-muted-foreground">
          <th className="pb-2 font-medium">Classification</th>
          <th className="pb-2 text-right font-medium">Rate</th>
          <th className="pb-2 text-right font-medium">vs. prior</th>
        </tr>
      </thead>
      <tbody>
        {CLASSIFICATION_ORDER.map((key) => {
          const rate = current[key] ?? 0;
          const d = delta?.[key] ?? null;
          // Higher is better only for best/good; the other three are costs.
          const higherIsBetter = key === 'best' || key === 'good';
          const isGood = d === null || d === 0 ? null : higherIsBetter ? d > 0 : d < 0;
          const deltaClass =
            d === null || d === 0
              ? 'text-muted-foreground'
              : isGood
                ? 'text-green-600 dark:text-green-500'
                : 'text-destructive';
          return (
            <tr key={key} className="border-t border-border">
              <td className={cn('py-2', CLASSIFICATION_CLASS[key])}>{CLASSIFICATION_LABEL[key]}</td>
              <td className="py-2 text-right tabular-nums">{formatPercent(rate)}</td>
              <td className={cn('py-2 text-right tabular-nums', deltaClass)}>
                {d === null ? '—' : `${d > 0 ? '+' : ''}${(d * 100).toFixed(1)} pts`}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
