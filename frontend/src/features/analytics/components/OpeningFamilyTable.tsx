import type { OpeningFamilyPerformance } from '../api/analytics';
import { formatPercent, formatPoints } from '../lib/format';

interface OpeningFamilyTableProps {
  families: OpeningFamilyPerformance[];
}

export function OpeningFamilyTable({ families }: OpeningFamilyTableProps) {
  if (families.length === 0) {
    return <p className="text-sm text-muted-foreground">No openings identified in this window.</p>;
  }
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-muted-foreground">
          <th className="pb-2 font-medium">Opening family</th>
          <th className="pb-2 text-right font-medium">Games</th>
          <th className="pb-2 text-right font-medium">W-D-L</th>
          <th className="pb-2 text-right font-medium">Win rate</th>
          <th className="pb-2 text-right font-medium">Avg. accuracy</th>
        </tr>
      </thead>
      <tbody>
        {families.map((f) => (
          <tr key={f.family} className="border-t border-border">
            <td className="py-2">{f.family}</td>
            <td className="py-2 text-right tabular-nums">{f.games}</td>
            <td className="py-2 text-right tabular-nums">
              {f.wins}-{f.draws}-{f.losses}
            </td>
            <td className="py-2 text-right tabular-nums">{formatPercent(f.win_rate)}</td>
            <td className="py-2 text-right tabular-nums">{formatPoints(f.average_accuracy)}%</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
