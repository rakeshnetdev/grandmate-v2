/**
 * Frontend configuration.
 *
 * All values come from Vite environment variables — nothing is hardcoded, matching the
 * backend contract in `final_docs/v2/configuration.md`.
 *
 * Only `VITE_`-prefixed values reach the browser, and only non-secret values belong
 * here. MVP login is username-claim (ADR-0014, deferring ADR-0007's Lichess OAuth2
 * PKCE), so there is no OAuth client id or redirect URI to configure yet — the frontend
 * only needs to know where the backend is.
 *
 * The schema is validated at module load so a misconfigured deployment fails
 * immediately with a clear message, rather than surfacing as a confusing 404 on the
 * first API call.
 */
import { z } from 'zod';

const envSchema = z.object({
  VITE_API_BASE_URL: z.string().url().default('http://localhost:7575'),
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
