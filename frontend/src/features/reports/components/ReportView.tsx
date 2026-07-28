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
 */
import { cn } from '@/shared/lib/utils';

import type { GameReport } from '../api/reports';

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

interface ReportViewProps {
  report: GameReport;
}

export function ReportView({ report }: ReportViewProps) {
  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm">{report.summary}</p>
        <SourceBadge source={report.source} />
      </div>

      {report.findings.length > 0 && (
        <ul className="space-y-2">
          {report.findings.map((finding, index) => (
            <li
              key={`${finding.fact_ids.join('-')}-${index}`}
              className={cn('rounded-md border border-border px-3 py-2 text-sm')}
            >
              {finding.text}
            </li>
          ))}
        </ul>
      )}

      {report.recommendations.length > 0 && (
        <div>
          <h3 className="mb-1 text-sm font-semibold">Recommendations</h3>
          <ul className="list-inside list-disc space-y-1 text-sm text-muted-foreground">
            {report.recommendations.map((recommendation) => (
              <li key={recommendation}>{recommendation}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
