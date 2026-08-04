/**
 * The full opening/middlegame/endgame game-story report (Phase 16b) — self-learner
 * only. Distinct from `ReportView`: a story is inherently sectioned (Opening/
 * Middlegame/Endgame/Lessons), so this always renders those named sections rather than
 * a flat findings list toggled by tag presence.
 *
 * Sections are bulleted with chess pieces rather than boxed in borders: a story is meant
 * to be read straight through, and stacked bordered panels made it look like a form to
 * fill in. Each phase gets a piece that fits it — a pawn opens, a knight does the
 * middlegame work, a king matters in the endgame, a queen carries the lesson — so the
 * marker orients the reader instead of just decorating.
 */
import { PieceList, PieceListItem } from '@/shared/components/ui/piece-list';
import type { ChessPiece } from '@/shared/components/ui/piece-list';
import { Prose } from '@/shared/lib/prose';

import type { GameReport, ReportFinding } from '../api/reports';
import { SourceBadge } from './SourceBadge';

const SECTION_ORDER = ['opening', 'middlegame', 'endgame', 'lesson'] as const;

const SECTION_LABELS: Record<(typeof SECTION_ORDER)[number], string> = {
  opening: 'Opening',
  middlegame: 'Middlegame',
  endgame: 'Endgame',
  lesson: 'Lessons',
};

const SECTION_PIECES: Record<(typeof SECTION_ORDER)[number], ChessPiece> = {
  opening: 'pawn',
  middlegame: 'knight',
  endgame: 'king',
  lesson: 'queen',
};

/** Muted per-phase tints, same restraint as the learning tiles — orientation, not alarm. */
const SECTION_TONES: Record<(typeof SECTION_ORDER)[number], string> = {
  opening: 'text-emerald-600/70 dark:text-emerald-400/70',
  middlegame: 'text-indigo-600/70 dark:text-indigo-400/70',
  endgame: 'text-amber-600/70 dark:text-amber-400/70',
  lesson: 'text-rose-600/70 dark:text-rose-400/70',
};

function Section({
  title,
  piece,
  tone,
  findings,
}: {
  title: string;
  piece: ChessPiece;
  tone: string;
  findings: ReportFinding[];
}) {
  if (findings.length === 0) {
    return null;
  }
  return (
    <section className="space-y-2">
      <h3 className="text-sm font-semibold">{title}</h3>
      <PieceList>
        {findings.map((finding, index) => (
          <PieceListItem key={`${finding.fact_ids.join('-')}-${index}`} piece={piece} tone={tone}>
            <Prose>{finding.text}</Prose>
          </PieceListItem>
        ))}
      </PieceList>
    </section>
  );
}

interface StoryViewProps {
  report: GameReport;
  /** Optional: when absent the badge renders without a regenerate control. */
  onRegenerate?: () => void;
  isRegenerating?: boolean;
}

export function StoryView({ report, onRegenerate, isRegenerating }: StoryViewProps) {
  const bySection = (kind: string) => report.findings.filter((finding) => finding.kind === kind);

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-3">
        <Prose className="flex-1">{report.summary}</Prose>
        <SourceBadge
          source={report.source}
          onRegenerate={onRegenerate}
          isRegenerating={isRegenerating}
          label="story"
        />
      </div>

      {SECTION_ORDER.map((kind) => (
        <Section
          key={kind}
          title={SECTION_LABELS[kind]}
          piece={SECTION_PIECES[kind]}
          tone={SECTION_TONES[kind]}
          findings={bySection(kind)}
        />
      ))}

      {report.recommendations.length > 0 && (
        <section className="space-y-2">
          <h3 className="text-sm font-semibold">Next Steps</h3>
          <PieceList>
            {report.recommendations.map((recommendation) => (
              <PieceListItem key={recommendation} piece="rook" tone="text-foreground/50">
                <Prose inline>{recommendation}</Prose>
              </PieceListItem>
            ))}
          </PieceList>
        </section>
      )}

      {report.findings.length === 0 && (
        <p className="text-sm text-muted-foreground">
          No story sections were generated for this game.
        </p>
      )}
    </div>
  );
}
