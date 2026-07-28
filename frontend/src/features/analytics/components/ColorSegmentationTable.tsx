import type { ColorSegment } from '../api/analytics';
import { formatPercent, formatPoints } from '../lib/format';

interface ColorSegmentationTableProps {
  segments: ColorSegment[];
}

export function ColorSegmentationTable({ segments }: ColorSegmentationTableProps) {
  if (segments.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No games with a determinable side in this window.
      </p>
    );
  }
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-muted-foreground">
          <th className="pb-2 font-medium">Side</th>
          <th className="pb-2 text-right font-medium">Games</th>
          <th className="pb-2 text-right font-medium">Win rate</th>
          <th className="pb-2 text-right font-medium">Avg. accuracy</th>
        </tr>
      </thead>
      <tbody>
        {segments.map((s) => (
          <tr key={s.color} className="border-t border-border">
            <td className="py-2 capitalize">{s.color}</td>
            <td className="py-2 text-right tabular-nums">{s.games}</td>
            <td className="py-2 text-right tabular-nums">{formatPercent(s.win_rate)}</td>
            <td className="py-2 text-right tabular-nums">{formatPoints(s.average_accuracy)}%</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
