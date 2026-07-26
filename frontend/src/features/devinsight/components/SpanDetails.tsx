/**
 * Attribute and token detail for the spans of one trace, grouped by kind.
 *
 * Groups replace the reference implementation's fixed tab bar. Tabs had to be declared up
 * front and sat empty until their phase landed; groups simply appear when a phase starts
 * emitting spans of that kind.
 */
import type { Span, SpanKind } from '../api/traces';

const KIND_LABEL: Record<SpanKind, string> = {
  http: 'HTTP',
  db: 'Database',
  engine: 'Engine',
  retrieval: 'Retrieval',
  llm: 'LLM',
  graph_node: 'Graph nodes',
  agent: 'Agents',
  grounding: 'Grounding',
  job: 'Jobs',
};

function groupByKind(spans: Span[]): [SpanKind, Span[]][] {
  const groups = new Map<SpanKind, Span[]>();
  for (const span of spans) {
    const existing = groups.get(span.kind);
    if (existing) {
      existing.push(span);
    } else {
      groups.set(span.kind, [span]);
    }
  }
  return [...groups.entries()];
}

export function SpanDetails({ spans }: { spans: Span[] }) {
  const groups = groupByKind(spans);

  if (groups.length === 0) {
    return null;
  }

  return (
    <div className="space-y-4">
      {groups.map(([kind, kindSpans]) => (
        <section key={kind}>
          <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {KIND_LABEL[kind]}
          </h4>
          <ul className="space-y-2">
            {kindSpans.map((span) => (
              <li key={span.span_id} className="rounded-md border border-border p-2 text-xs">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="font-medium">{span.name}</span>
                  <span className="text-muted-foreground">{span.duration_ms.toFixed(1)}ms</span>
                </div>

                {span.error && <p className="mt-1 text-destructive">{span.error}</p>}

                {span.tokens && (
                  <p className="mt-1 text-muted-foreground">
                    {span.tokens.prompt_tokens} prompt + {span.tokens.completion_tokens} completion
                    tokens
                  </p>
                )}

                {Object.keys(span.attributes).length > 0 && (
                  <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-2 gap-y-0.5">
                    {Object.entries(span.attributes).map(([key, value]) => (
                      <div key={key} className="contents">
                        <dt className="text-muted-foreground">{key}</dt>
                        <dd className="break-all font-mono">{String(value)}</dd>
                      </div>
                    ))}
                  </dl>
                )}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
