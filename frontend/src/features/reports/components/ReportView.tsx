/**
 * One persona's rendered report (Phase 9): a summary, capped/ranked findings, and
 * recommendations — the same underlying facts as the deterministic analysis view,
 * phrased for the selected audience. Never a different truth, per `persona-matrix.md`'s
 * invariant.
 *
 * `source` is shown, not hidden: "Deterministic summary" for a `fallback` report is not
 * an error state (see `domain/reports/fallback.py`'s own docstring) but it *is*
 * something a reader benefits from knowing, the same transparency reasoning
 * `claude.md`'s RAG rules apply everywhere else an LLM claim could be wrong.
 *
 * Phase 16a, D-035 addendum: self-learner reports tag each finding "strength" or
 * "mistake" (backend: `domain/reports/critic.py`'s kind check). When that tagging is
 * present, findings render grouped under "What Went Well" / "Mistakes & Blunders"
 * headers instead of one flat list — coach and kid reports never carry this tag, so they
 * keep the original flat rendering untouched.
 */
import { Prose } from '@/shared/lib/prose';

import type { GameReport, ReportFinding } from '../api/reports';
import { SourceBadge } from './SourceBadge';

function FindingList({ findings }: { findings: ReportFinding[] }) {
  return (
    <ul className="list-inside list-disc space-y-1">
      {findings.map((finding, index) => (
        <li key={`${finding.fact_ids.join('-')}-${index}`}>
          <Prose inline>{finding.text}</Prose>
        </li>
      ))}
    </ul>
  );
}

function FindingGroup({ title, findings }: { title: string; findings: ReportFinding[] }) {
  if (findings.length === 0) {
    return null;
  }
  return (
    <div className="space-y-1">
      <h3 className="text-sm font-semibold">{title}</h3>
      <FindingList findings={findings} />
    </div>
  );
}

interface ReportViewProps {
  report: GameReport;
  /** Optional: when absent the badge renders without a regenerate control. */
  onRegenerate?: () => void;
  isRegenerating?: boolean;
}

export function ReportView({ report, onRegenerate, isRegenerating }: ReportViewProps) {
  const hasKindTags = report.findings.some((finding) => finding.kind != null);
  const strengths = report.findings.filter((finding) => finding.kind === 'strength');
  const mistakes = report.findings.filter((finding) => finding.kind === 'mistake');

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 space-y-1">
          {hasKindTags && <h3 className="text-sm font-semibold">Overview</h3>}
          <Prose>{report.summary}</Prose>
        </div>
        <SourceBadge
          source={report.source}
          onRegenerate={onRegenerate}
          isRegenerating={isRegenerating}
          label="report"
        />
      </div>

      {hasKindTags ? (
        <>
          <FindingGroup title="What Went Well" findings={strengths} />
          <FindingGroup title="Mistakes & Blunders" findings={mistakes} />
        </>
      ) : (
        report.findings.length > 0 && <FindingList findings={report.findings} />
      )}

      {report.recommendations.length > 0 && (
        <div>
          <h3 className="mb-1 text-sm font-semibold">
            {hasKindTags ? 'Strategy to Improve' : 'Recommendations'}
          </h3>
          <ul className="list-inside list-disc space-y-1 text-muted-foreground">
            {report.recommendations.map((recommendation) => (
              <li key={recommendation}>
                <Prose inline>{recommendation}</Prose>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
