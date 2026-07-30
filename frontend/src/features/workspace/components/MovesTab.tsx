/**
 * Move-by-move engine evaluation for the selected game (Phase 16a, D-035) — the
 * workspace's "Moves" tab. Adapted from `features/games/components/GameAnalysisView.tsx`
 * (which stays in place for now, retired once the workspace fully replaces the standalone
 * game-detail page): real SAN notation (D-035's backend addition) instead of ply/UCI
 * labels, and `ClassificationBadge`'s pill styling instead of plain colored text.
 */
import { useGame, useGameAnalysis } from '@/features/games';
import type { GameAnalysis, MoveEvaluation } from '@/features/games';
import { ClassificationBadge } from '@/shared/components/ui/classification-badge';
import { cn } from '@/shared/lib/utils';

function moveLabel(ply: number): string {
  const moveNumber = Math.floor(ply / 2) + 1;
  return ply % 2 === 0 ? `${moveNumber}.` : `${moveNumber}…`;
}

function evalLabel(move: MoveEvaluation): string {
  if (move.mate_in !== null) {
    return `M${move.mate_in}`;
  }
  if (move.eval_cp === null) {
    return '—';
  }
  const pawns = move.eval_cp / 100;
  return `${pawns >= 0 ? '+' : ''}${pawns.toFixed(1)}`;
}

function AnalysisSummaryBar({ analysis }: { analysis: GameAnalysis }) {
  const { summary } = analysis;
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
      <span className="font-medium">{summary.accuracy}% accuracy</span>
      <span className="text-muted-foreground">{summary.total_moves} moves</span>
      <span className="text-muted-foreground">{summary.critical_moments} critical moments</span>
    </div>
  );
}

function MoveList({ moves }: { moves: MoveEvaluation[] }) {
  return (
    <ul className="divide-y divide-border rounded-md border border-border">
      {moves.map((move) => (
        <li
          key={move.ply}
          className={cn(
            'flex items-center justify-between gap-3 px-3 py-2 text-sm',
            move.is_critical_moment && 'bg-accent/50',
          )}
        >
          <span className="w-14 shrink-0 text-muted-foreground">{moveLabel(move.ply)}</span>
          <span className="flex-1 font-mono font-medium">{move.san ?? '—'}</span>
          <span className="w-14 shrink-0 text-xs text-muted-foreground">
            {move.best_move_uci ? `best: ${move.best_move_uci}` : ''}
          </span>
          <span className="w-16 shrink-0 text-right font-mono tabular-nums">{evalLabel(move)}</span>
          <ClassificationBadge classification={move.classification} className="w-20 shrink-0" />
        </li>
      ))}
    </ul>
  );
}

interface MovesTabProps {
  gameId: string;
  profileId?: string;
}

export function MovesTab({ gameId, profileId }: MovesTabProps) {
  const { data: game } = useGame(gameId, profileId);
  const { data: analysis, isLoading, isError } = useGameAnalysis(gameId, profileId);

  if (game && game.canonicalized_at === null) {
    return (
      <p className="text-sm text-muted-foreground">
        This game could not be parsed, so no analysis is available for it.
      </p>
    );
  }

  // Distinct from "still loading" (Phase 16a) — a real fetch/parse error left showing
  // "Analyzing…" forever would look identical to a slow-but-working poll, with no way
  // for a reader to tell the two apart.
  if (isError) {
    return <p className="text-sm text-destructive">Could not load this game's move analysis.</p>;
  }

  if (isLoading || !analysis) {
    return (
      <p className="text-sm text-muted-foreground">
        Analyzing this game with Stockfish — this usually takes a few seconds…
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <AnalysisSummaryBar analysis={analysis} />
      <MoveList moves={analysis.moves} />
    </div>
  );
}
