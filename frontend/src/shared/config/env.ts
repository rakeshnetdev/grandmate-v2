/**
 * Frontend configuration.
 *
 * All values come from Vite environment variables — nothing is hardcoded, matching the
 * backend contract in `final_docs/v2/configuration.md`.
 *
 * Only `VITE_`-prefixed values reach the browser, and only non-secret values belong
 * here. The Lichess client id is public by design (ADR-0007: Lichess is a public OAuth
 * client with no secret). Anything that genuinely needs protecting lives behind the
 * backend.
 *
 * The schema is validated at module load so a misconfigured deployment fails
 * immediately with a clear message, rather than surfacing as a confusing 404 on the
 * first API call.
 */
import { z } from 'zod';

const envSchema = z.object({
  VITE_API_BASE_URL: z.string().url().default('http://localhost:8000'),
  VITE_LICHESS_CLIENT_ID: z.string().min(1).default('grandmate-v2'),
  VITE_LICHESS_REDIRECT_URI: z.string().url().default('http://localhost:5173/auth/callback'),
});

function loadEnv() {
  const parsed = envSchema.safeParse(import.meta.env);

  if (!parsed.success) {
    // Report every problem at once rather than one per reload.
    const issues = parsed.error.issues
      .map((issue) => `  ${issue.path.join('.')}: ${issue.message}`)
      .join('\n');
    throw new Error(`Invalid frontend environment configuration:\n${issues}`);
  }

  return parsed.data;
}

export const env = loadEnv();

export type Env = typeof env;
