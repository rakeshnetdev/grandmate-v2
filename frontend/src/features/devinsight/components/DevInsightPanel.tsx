/**
 * Developer insight panel.
 *
 * A collapsed footer bar that expands into a trace inspector. Two deliberate properties:
 *
 * - **Nothing is fetched until it is opened.** Closed, this component issues no requests
 *   at all, which is what keeps tracing free for developers who are not looking at it.
 * - **It disappears when the backend has tracing off.** The dev endpoints do not exist in
 *   production, so a failed trace list is treated as "tracing is disabled" and the panel
 *   hides itself rather than showing an error nobody can act on.
 */
import { useState } from 'react';

import { Button } from '@/shared/components/ui/button';

import { useTrace, useTraces } from '../hooks/useTraces';
import { SpanDetails } from './SpanDetails';
import { SpanTimeline } from './SpanTimeline';

export function DevInsightPanel() {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);

  const { data: traces, isError } = useTraces(isOpen);
  const { data: trace } = useTrace(selectedTraceId);

  // Tracing is off on this backend (the routes 404). Nothing useful to show.
  if (isOpen && isError) {
    return (
      <div className="border-t border-border bg-card px-6 py-2 text-xs text-muted-foreground">
        Developer insight is disabled on this backend. Set{' '}
        <code className="font-mono">DEV_INSIGHT_ENABLED=true</code> to enable it.
      </div>
    );
  }

  if (!isOpen) {
    return (
      <div className="border-t border-border bg-card px-6 py-2">
        <Button variant="ghost" size="sm" onClick={() => setIsOpen(true)}>
          Developer insight
        </Button>
      </div>
    );
  }

  return (
    <div className="border-t border-border bg-card">
      <div className="flex items-center justify-between px-6 py-2">
        <h3 className="text-sm font-semibold">Developer insight</h3>
        <Button variant="ghost" size="sm" onClick={() => setIsOpen(false)}>
          Close
        </Button>
      </div>

      <div className="grid max-h-96 grid-cols-1 gap-4 overflow-y-auto px-6 pb-4 sm:grid-cols-[16rem_1fr]">
        <div>
          <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Requests
          </h4>
          <ul className="space-y-0.5">
            {traces?.map((summary) => (
              <li key={summary.trace_id}>
                <button
                  type="button"
                  onClick={() => setSelectedTraceId(summary.trace_id)}
                  className={`w-full rounded px-2 py-1 text-left text-xs hover:bg-accent ${
                    selectedTraceId === summary.trace_id ? 'bg-accent' : ''
                  }`}
                >
                  <span className="block truncate font-medium">{summary.label}</span>
                  <span className="text-muted-foreground">
                    {summary.duration_ms.toFixed(0)}ms · {summary.span_count} spans
                    {summary.total_tokens > 0 && ` · ${summary.total_tokens} tok`}
                  </span>
                </button>
              </li>
            ))}
            {traces?.length === 0 && (
              <li className="px-2 text-xs text-muted-foreground">No requests recorded yet.</li>
            )}
          </ul>
        </div>

        <div className="space-y-4">
          {trace ? (
            <>
              <div>
                <div className="flex items-baseline justify-between">
                  <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Timeline
                  </h4>
                  <span className="text-xs text-muted-foreground">
                    {trace.duration_ms.toFixed(1)}ms total
                  </span>
                </div>
                {trace.truncated && (
                  <p className="mt-1 text-xs text-destructive">
                    Span limit reached — this trace is incomplete.
                  </p>
                )}
                <div className="mt-2">
                  <SpanTimeline spans={trace.spans} totalDurationMs={trace.duration_ms} />
                </div>
              </div>

              <SpanDetails spans={trace.spans} />
            </>
          ) : (
            <p className="text-xs text-muted-foreground">Select a request to inspect it.</p>
          )}
        </div>
      </div>
    </div>
  );
}
