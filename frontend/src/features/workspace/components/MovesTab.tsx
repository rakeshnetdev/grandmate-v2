/**
 * Move-by-move engine evaluation for the selected game (Phase 16a, D-035) — the
 * workspace's "Moves" tab. Two-column layout (Phase 16b follow-up): one row per full
 * move, White's ply on the left and Black's reply on the right, with a header naming
 * each player — mirrors how a printed score sheet reads, instead of one long
 * alternating list where the repeated move numbers (`1.` / `1…`) confused readers.
 */
import { useGame, useGameAnalysis } from '@/features/games';
import type { GameAnalysis, MoveEvaluation } from '@/features/games';
import { ClassificationBadge } from '@/shared/components/ui/classification-badge';
import { cn } from '@/shared/lib/utils';

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

const MISTAKE_TIER = new Set(['inaccuracy', 'mistake', 'blunder']);

function PlyCell({ move }: { move: MoveEvaluation | undefined }) {
  // A game can end on White's move, leaving the final row's Black cell empty.
  if (!move) {
    return <div className="flex-1 px-3 py-2" />;
  }
  // The engine's suggestion is only worth showing where the played move fell short —
  // on a best/good move it would just restate (or nitpick) the move itself.
  const showBest = MISTAKE_TIER.has(move.classification) && move.best_move_san;
  return (
    <div
      className={cn(
        'flex flex-1 items-center gap-2 px-3 py-2 text-sm',
        move.is_critical_moment && 'bg-accent/50',
      )}
    >
      <span className="w-14 shrink-0 font-mono font-medium">{move.san ?? '—'}</span>
      <span className="w-12 shrink-0 text-right font-mono text-xs tabular-nums text-muted-foreground">
        {evalLabel(move)}
      </span>
      <ClassificationBadge classification={move.classification} className="shrink-0" />
      {showBest && (
        <span className="shrink-0 text-xs text-muted-foreground">
          best: <span className="font-mono">{move.best_move_san}</span>
        </span>
      )}
    </div>
  );
}

interface MoveListProps {
  moves: MoveEvaluation[];
  whiteName: string;
  blackName: string;
}

function MoveList({ moves, whiteName, blackName }: MoveListProps) {
  // Pair plies into full moves: even ply = White, odd ply = Black. Keyed by ply rather
  // than array position so a gap (which should not happen) can't silently mispair.
  const byPly = new Map(moves.map((move) => [move.ply, move]));
  const moveCount = Math.ceil((Math.max(...moves.map((m) => m.ply)) + 1) / 2);
  const rows = Array.from({ length: moveCount }, (_, i) => ({
    number: i + 1,
    white: byPly.get(i * 2),
    black: byPly.get(i * 2 + 1),
  }));

  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <div className="min-w-[28rem]">
        <div className="flex border-b border-border bg-muted/50 text-xs font-semibold">
          <span className="w-10 shrink-0 px-2 py-2 text-muted-foreground">#</span>
          <span className="flex-1 px-3 py-2">{whiteName} (White)</span>
          <span className="flex-1 border-l border-border px-3 py-2">{blackName} (Black)</span>
        </div>
        <ul className="divide-y divide-border">
          {rows.map((row) => (
            <li key={row.number} className="flex items-stretch">
              <span className="w-10 shrink-0 px-2 py-2 text-sm text-muted-foreground">
                {row.number}.
              </span>
              <PlyCell move={row.white} />
              <div className="w-px shrink-0 bg-border" />
              <PlyCell move={row.black} />
            </li>
          ))}
        </ul>
      </div>
    </div>
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
      <MoveList
        moves={analysis.moves}
        whiteName={game?.headers['White'] ?? 'White'}
        blackName={game?.headers['Black'] ?? 'Black'}
      />
    </div>
  );
}
