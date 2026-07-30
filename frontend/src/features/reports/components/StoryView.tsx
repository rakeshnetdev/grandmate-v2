/**
 * The full opening/middlegame/endgame game-story report (Phase 16b) — self-learner
 * only. Distinct from `ReportView`: a story is inherently sectioned (Opening/
 * Middlegame/Endgame/Lessons), so this always renders those named sections rather than
 * a flat findings list toggled by tag presence.
 */
import { Prose } from '@/shared/lib/prose';

import type { GameReport, ReportFinding } from '../api/reports';

const SECTION_ORDER = ['opening', 'middlegame', 'endgame', 'lesson'] as const;
const SECTION_LABELS: Record<(typeof SECTION_ORDER)[number], string> = {
  opening: 'Opening',
  middlegame: 'Middlegame',
  endgame: 'Endgame',
  lesson: 'Lessons',
};

function SourceBadge({ source }: { source: GameReport['source'] }) {
  if (source === 'fallback') {
    return (
      <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
        Deterministic summary
      </span>
    );
  }
  return (
    <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
      AI-generated
    </span>
  );
}

function Section({ title, findings }: { title: string; findings: ReportFinding[] }) {
  if (findings.length === 0) {
    return null;
  }
  return (
    <div className="space-y-2 rounded-lg border border-border p-3">
      <h3 className="text-sm font-semibold">{title}</h3>
      <div className="space-y-2">
        {findings.map((finding, index) => (
          <Prose key={`${finding.fact_ids.join('-')}-${index}`}>{finding.text}</Prose>
        ))}
      </div>
    </div>
  );
}

interface StoryViewProps {
  report: GameReport;
}

export function StoryView({ report }: StoryViewProps) {
  const bySection = (kind: string) => report.findings.filter((finding) => finding.kind === kind);

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <Prose className="flex-1">{report.summary}</Prose>
        <SourceBadge source={report.source} />
      </div>

      {SECTION_ORDER.map((kind) => (
        <Section key={kind} title={SECTION_LABELS[kind]} findings={bySection(kind)} />
      ))}

      {report.recommendations.length > 0 && (
        <div>
          <h3 className="mb-1 text-sm font-semibold">Next Steps</h3>
          <ul className="list-inside list-disc space-y-1 text-muted-foreground">
            {report.recommendations.map((recommendation) => (
              <li key={recommendation}>
                <Prose inline>{recommendation}</Prose>
              </li>
            ))}
          </ul>
        </div>
      )}

      {report.findings.length === 0 && (
        <p className="text-sm text-muted-foreground">
          No story sections were generated for this game.
        </p>
      )}
    </div>
  );
}
