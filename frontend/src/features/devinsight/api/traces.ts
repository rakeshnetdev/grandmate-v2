/**
 * Developer insight API contract.
 *
 * Mirrors `backend/app/core/devinsight/models.py`. These endpoints exist only when the
 * backend has developer insight enabled — they are absent in production — so callers must
 * treat a 404 as "tracing is off", not as an error worth surfacing.
 */
import { z } from 'zod';

import { apiClient } from '@/shared/lib/api-client';

export const spanKindSchema = z.enum([
  'http',
  'db',
  'engine',
  'retrieval',
  'llm',
  'graph_node',
  'agent',
  'grounding',
  'job',
]);

export const tokenCountSchema = z.object({
  prompt_tokens: z.number(),
  completion_tokens: z.number(),
});

export const spanSchema = z.object({
  span_id: z.string(),
  parent_span_id: z.string().nullable(),
  kind: spanKindSchema,
  name: z.string(),
  started_at: z.string(),
  duration_ms: z.number(),
  status: z.enum(['ok', 'error']),
  error: z.string().nullable(),
  attributes: z.record(z.string(), z.unknown()),
  tokens: tokenCountSchema.nullable(),
});

export const traceSchema = z.object({
  trace_id: z.string(),
  label: z.string(),
  started_at: z.string(),
  duration_ms: z.number(),
  status: z.enum(['ok', 'error']),
  spans: z.array(spanSchema),
  truncated: z.boolean(),
});

export const traceSummarySchema = z.object({
  trace_id: z.string(),
  label: z.string(),
  started_at: z.string(),
  duration_ms: z.number(),
  status: z.enum(['ok', 'error']),
  span_count: z.number(),
  total_tokens: z.number(),
});

export type SpanKind = z.infer<typeof spanKindSchema>;
export type Span = z.infer<typeof spanSchema>;
export type Trace = z.infer<typeof traceSchema>;
export type TraceSummary = z.infer<typeof traceSummarySchema>;

const traceListSchema = z.array(traceSummarySchema);

export function fetchTraces(signal?: AbortSignal): Promise<TraceSummary[]> {
  return apiClient.get('/api/v1/dev/traces?limit=50', traceListSchema, signal);
}

export function fetchTrace(traceId: string, signal?: AbortSignal): Promise<Trace> {
  return apiClient.get(`/api/v1/dev/traces/${traceId}`, traceSchema, signal);
}
