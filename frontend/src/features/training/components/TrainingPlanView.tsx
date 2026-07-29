/**
 * One generated training plan (Phase 15, D-032): a summary, findings grounded in the
 * profile's own recurring weaknesses plus cited study material, and recommendations —
 * same source-transparency reasoning `features/reports/components/ReportView.tsx`
 * documents (an LLM claim's provenance is never hidden from the reader).
 */
import { cn } from '@/shared/lib/utils';

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
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm">{plan.summary}</p>
        <SourceBadge source={plan.source} />
      </div>

      {plan.findings.length > 0 && (
        <ul className="space-y-2">
          {plan.findings.map((finding, index) => (
            <li
              key={`${finding.fact_ids.join('-')}-${index}`}
              className={cn('rounded-md border border-border px-3 py-2 text-sm')}
            >
              {finding.text}
            </li>
          ))}
        </ul>
      )}

      {plan.recommendations.length > 0 && (
        <div>
          <h3 className="mb-1 text-sm font-semibold">This week's focus</h3>
          <ul className="list-inside list-disc space-y-1 text-sm text-muted-foreground">
            {plan.recommendations.map((recommendation) => (
              <li key={recommendation}>{recommendation}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
