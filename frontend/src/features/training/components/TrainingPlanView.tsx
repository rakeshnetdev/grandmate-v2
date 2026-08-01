/**
 * One generated training plan (Phase 15, D-032): a summary, findings grounded in the
 * profile's own recurring weaknesses plus cited study material, and recommendations —
 * same source-transparency reasoning `features/reports/components/ReportView.tsx`
 * documents (an LLM claim's provenance is never hidden from the reader).
 *
 * Findings are bulleted with chess pieces rather than boxed in borders. A stack of
 * bordered rows read as a list of problems; the same text as knight-marked points reads
 * as a list of things to work on, which is what a training plan is meant to be.
 */
import { PieceList, PieceListItem } from '@/shared/components/ui/piece-list';
import { Prose } from '@/shared/lib/prose';

import type { TrainingRecommendation } from '../api/training';

function SourceBadge({ source }: { source: TrainingRecommendation['source'] }) {
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

interface TrainingPlanViewProps {
  plan: TrainingRecommendation;
}

export function TrainingPlanView({ plan }: TrainingPlanViewProps) {
  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-3">
        <Prose className="flex-1">{plan.summary}</Prose>
        <SourceBadge source={plan.source} />
      </div>

      {plan.findings.length > 0 && (
        <PieceList>
          {plan.findings.map((finding, index) => (
            <PieceListItem
              key={`${finding.fact_ids.join('-')}-${index}`}
              piece="knight"
              tone="text-indigo-600/70 dark:text-indigo-400/70"
            >
              <Prose>{finding.text}</Prose>
            </PieceListItem>
          ))}
        </PieceList>
      )}

      {plan.recommendations.length > 0 && (
        <section className="space-y-2">
          <h3 className="text-sm font-semibold">This week&apos;s focus</h3>
          <PieceList>
            {plan.recommendations.map((recommendation) => (
              <PieceListItem
                key={recommendation}
                piece="pawn"
                tone="text-emerald-600/70 dark:text-emerald-400/70"
              >
                <Prose inline>{recommendation}</Prose>
              </PieceListItem>
            ))}
          </PieceList>
        </section>
      )}
    </div>
  );
}
