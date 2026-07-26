/**
 * Span timeline for one trace.
 *
 * Bars are scaled against the trace's total duration, so what stands out visually is
 * where the time actually went — which is the first question anyone opens a tracing panel
 * to answer.
 */
import type { Span, SpanKind } from '../api/traces';

/** Tailwind class per span kind. Colour carries the grouping, so tabs are not needed. */
const KIND_COLOUR: Record<SpanKind, string> = {
  http: 'bg-slate-400',
  db: 'bg-amber-500',
  engine: 'bg-emerald-500',
  retrieval: 'bg-sky-500',
  llm: 'bg-violet-500',
  graph_node: 'bg-indigo-500',
  agent: 'bg-fuchsia-500',
  grounding: 'bg-teal-500',
  job: 'bg-orange-500',
};

interface SpanTimelineProps {
  spans: Span[];
  totalDurationMs: number;
}

export function SpanTimeline({ spans, totalDurationMs }: SpanTimelineProps) {
  if (spans.length === 0) {
    return <p className="text-sm text-muted-foreground">No spans recorded.</p>;
  }

  // Guard against a zero-duration trace producing NaN widths.
  const scale = totalDurationMs > 0 ? totalDurationMs : 1;

  return (
    <ul className="space-y-1">
      {spans.map((span) => {
        const widthPercent = Math.max((span.duration_ms / scale) * 100, 1);
        const isNested = span.parent_span_id !== null;

        return (
          <li key={span.span_id} className="text-xs">
            <div className="flex items-baseline gap-2">
              <span className={isNested ? 'pl-3 text-muted-foreground' : 'font-medium'}>
                {span.name}
              </span>
              <span className="text-muted-foreground">{span.duration_ms.toFixed(1)}ms</span>
              {span.status === 'error' && <span className="text-destructive">error</span>}
              {span.tokens && (
                <span className="text-muted-foreground">
                  {span.tokens.prompt_tokens + span.tokens.completion_tokens} tok
                </span>
              )}
            </div>
            <div className="mt-0.5 h-1.5 w-full rounded-full bg-muted">
              <div
                className={`h-full rounded-full ${KIND_COLOUR[span.kind]}`}
                style={{ width: `${widthPercent}%` }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}
