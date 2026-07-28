import type { TimeControlSegment } from '../api/analytics';
import { formatPercent, formatPoints } from '../lib/format';

interface TimeControlTableProps {
  segments: TimeControlSegment[];
}

export function TimeControlTable({ segments }: TimeControlTableProps) {
  if (segments.length === 0) {
    return <p className="text-sm text-muted-foreground">No games in this window.</p>;
  }
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-muted-foreground">
          <th className="pb-2 font-medium">Time control</th>
          <th className="pb-2 text-right font-medium">Games</th>
          <th className="pb-2 text-right font-medium">Win rate</th>
          <th className="pb-2 text-right font-medium">Avg. accuracy</th>
        </tr>
      </thead>
      <tbody>
        {segments.map((s) => (
          <tr key={s.bucket} className="border-t border-border">
            <td className="py-2 capitalize">{s.bucket}</td>
            <td className="py-2 text-right tabular-nums">{s.games}</td>
            <td className="py-2 text-right tabular-nums">{formatPercent(s.win_rate)}</td>
            <td className="py-2 text-right tabular-nums">{formatPoints(s.average_accuracy)}%</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
