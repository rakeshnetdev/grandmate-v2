/**
 * One game's deterministic analysis: engine evaluation per move, opening identification,
 * and tactical/strategic findings. Everything here comes straight from Phase 5/6's
 * already-computed data — there is no LLM narrative anywhere in this view (Phase 7 built
 * RAG retrieval infrastructure, but nothing yet consumes it to explain a game; that
 * lands with Phase 9/10's persona and chat work).
 *
 * Moves are labelled by ply/side rather than SAN notation (e.g. "Nf3") — the analysis
 * endpoint carries evaluations, not move text, and Phase 4 deliberately left a
 * canonical-moves route out of scope. Best-move suggestions are shown in UCI form
 * (`e2e4`) for the same reason.
 */
import { cn } from '@/shared/lib/utils';

import type { GameAnalysis, GamePatterns, MoveEvaluation } from '../api/games';
import { useGame, useGameAnalysis, useGamePatterns } from '../hooks/useGames';

const CLASSIFICATION_LABEL: Record<MoveEvaluation['classification'], string> = {
  best: 'Best',
  good: 'Good',
  inaccuracy: 'Inaccuracy',
  mistake: 'Mistake',
  blunder: 'Blunder',
};

const CLASSIFICATION_CLASS: Record<MoveEvaluation['classification'], string> = {
  best: 'text-green-600 dark:text-green-500',
  good: 'text-emerald-600 dark:text-emerald-500',
  inaccuracy: 'text-yellow-600 dark:text-yellow-500',
  mistake: 'text-orange-600 dark:text-orange-500',
  blunder: 'text-destructive',
};

// `ply` is 0-indexed from `canonicalize_pgn` (`enumerate(game.mainline())`), so ply 0 is
// White's first move, not Black's — see `domain/games/parsing.py`.
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
      <span className="text-muted-foreground">
        {Object.entries(summary.counts)
          .filter(([, count]) => count > 0)
          .map(([classification, count]) => `${count} ${classification}`)
          .join(' · ')}
      </span>
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
          <span className="flex-1 text-xs text-muted-foreground">
            {move.best_move_uci ? `best: ${move.best_move_uci}` : ''}
          </span>
          <span
            className={cn(
              'w-16 shrink-0 text-right font-mono',
              CLASSIFICATION_CLASS[move.classification],
            )}
          >
            {evalLabel(move)}
          </span>
          <span
            className={cn('w-20 shrink-0 text-right', CLASSIFICATION_CLASS[move.classification])}
          >
            {CLASSIFICATION_LABEL[move.classification]}
          </span>
        </li>
      ))}
    </ul>
  );
}

function PatternsSummary({ patterns }: { patterns: GamePatterns }) {
  if (!patterns.opening && patterns.motifs.length === 0 && patterns.themes.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">No opening match or findings for this game.</p>
    );
  }

  return (
    <div className="space-y-2 text-sm">
      {patterns.opening && (
        <p>
          <span className="font-medium">{patterns.opening.opening_name}</span>{' '}
          <span className="text-muted-foreground">({patterns.opening.eco})</span>
        </p>
      )}
      {patterns.motifs.length > 0 && (
        <p className="text-muted-foreground">
          Tactical motifs: {patterns.motifs.map((m) => `${m.motif} (ply ${m.ply})`).join(', ')}
        </p>
      )}
      {patterns.themes.length > 0 && (
        <p className="text-muted-foreground">
          Strategic themes: {patterns.themes.map((t) => `${t.theme} (ply ${t.ply})`).join(', ')}
        </p>
      )}
    </div>
  );
}

interface GameAnalysisViewProps {
  gameId: string;
}

export function GameAnalysisView({ gameId }: GameAnalysisViewProps) {
  const { data: game } = useGame(gameId);
  const { data: analysis, isLoading: analysisLoading } = useGameAnalysis(gameId);
  const { data: patterns } = useGamePatterns(gameId, { enabled: Boolean(analysis) });

  if (game && game.canonicalized_at === null) {
    return (
      <p className="text-sm text-muted-foreground">
        This game could not be parsed, so no analysis is available for it.
      </p>
    );
  }

  if (analysisLoading || !analysis) {
    return (
      <p className="text-sm text-muted-foreground">
        Analyzing this game with Stockfish — this usually takes a few seconds…
      </p>
    );
  }

  return (
    <div className="space-y-6">
      <AnalysisSummaryBar analysis={analysis} />

      {patterns && (
        <div>
          <h2 className="mb-2 text-sm font-semibold">Opening &amp; patterns</h2>
          <PatternsSummary patterns={patterns} />
        </div>
      )}

      <div>
        <h2 className="mb-2 text-sm font-semibold">Move-by-move evaluation</h2>
        <MoveList moves={analysis.moves} />
      </div>
    </div>
  );
}
