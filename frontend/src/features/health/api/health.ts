/**
 * Health API contract.
 *
 * The Zod schemas here mirror `backend/app/schemas/health.py`. They are the typed
 * contract at the boundary: `HealthStatus` is inferred from the schema, so the TypeScript
 * type and the runtime validation can never disagree.
 *
 * From Phase 2, generating these from the backend's OpenAPI schema is worth revisiting.
 * Hand-written is fine for two endpoints; it will not stay fine.
 */
import { z } from 'zod';

import { apiClient } from '@/shared/lib/api-client';

export const healthSchema = z.object({
  status: z.literal('ok'),
  service: z.string(),
  version: z.string(),
});

export const readinessSchema = z.object({
  status: z.enum(['ready', 'not_ready']),
  environment: z.string(),
  missing_configuration: z.array(z.string()),
  checks: z.record(z.string(), z.boolean()),
});

export type HealthStatus = z.infer<typeof healthSchema>;
export type ReadinessStatus = z.infer<typeof readinessSchema>;

export function fetchHealth(signal?: AbortSignal): Promise<HealthStatus> {
  return apiClient.get('/health', healthSchema, signal);
}

export function fetchReadiness(signal?: AbortSignal): Promise<ReadinessStatus> {
  return apiClient.get('/ready', readinessSchema, signal);
}
