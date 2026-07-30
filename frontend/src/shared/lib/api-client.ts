/**
 * Centralised API client.
 *
 * Presentation components never call `fetch` directly — they use feature hooks, which
 * use feature API modules, which use this client. That layering keeps network concerns
 * (base URL, credentials, error shaping, and later auth headers) in one place instead of
 * scattered through the component tree.
 *
 * Responses are validated with a Zod schema at the boundary. An API that changes shape
 * should fail loudly here with a useful message, not silently render `undefined` three
 * components deep.
 */
import { z } from 'zod';

import { env } from '@/shared/config/env';

// Fields are declared and assigned explicitly rather than using constructor parameter
// properties: `erasableSyntaxOnly` is enabled, and parameter properties emit runtime code.

/** Error thrown for any non-2xx response. */
export class ApiError extends Error {
  readonly status: number;
  readonly path: string;
  readonly body: unknown;

  constructor(message: string, status: number, path: string, body?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.path = path;
    this.body = body;
  }
}

/** Error thrown when a response does not match the expected schema. */
export class ApiSchemaError extends Error {
  readonly path: string;
  readonly issues: z.ZodIssue[];

  constructor(path: string, issues: z.ZodIssue[]) {
    super(`Unexpected response shape from ${path}`);
    this.name = 'ApiSchemaError';
    this.path = path;
    this.issues = issues;
  }
}

interface RequestOptions<TSchema extends z.ZodTypeAny> {
  /** Schema the response body must satisfy. */
  schema: TSchema;
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE';
  body?: unknown;
  signal?: AbortSignal;
}

async function request<TSchema extends z.ZodTypeAny>(
  path: string,
  { schema, method = 'GET', body, signal }: RequestOptions<TSchema>,
): Promise<z.infer<TSchema>> {
  const url = `${env.VITE_API_BASE_URL}${path}`;

  // `FormData` (multipart upload, e.g. PGN import) must not get a JSON Content-Type or a
  // JSON.stringify body — the browser sets the multipart boundary header itself only when
  // Content-Type is left unset.
  const isFormData = body instanceof FormData;

  const response = await fetch(url, {
    method,
    signal,
    headers: body && !isFormData ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? (isFormData ? body : JSON.stringify(body)) : undefined,
    // Session cookies are issued by our own backend (ADR-0007), so credentials travel.
    credentials: 'include',
  });

  // Read the body once; it may be useful error context even on failure.
  const raw: unknown = await response.json().catch(() => undefined);

  if (!response.ok) {
    throw new ApiError(
      `Request to ${path} failed with ${response.status}`,
      response.status,
      path,
      raw,
    );
  }

  const parsed = schema.safeParse(raw);
  if (!parsed.success) {
    throw new ApiSchemaError(path, parsed.error.issues);
  }

  return parsed.data;
}

/** Fetches a plain-text endpoint (e.g. a game's raw PGN) — no Zod schema, since there
 * is no JSON structure to validate; non-2xx still throws `ApiError`. */
async function requestText(path: string, signal?: AbortSignal): Promise<string> {
  const response = await fetch(`${env.VITE_API_BASE_URL}${path}`, {
    signal,
    credentials: 'include',
  });
  if (!response.ok) {
    const raw: unknown = await response.json().catch(() => undefined);
    throw new ApiError(
      `Request to ${path} failed with ${response.status}`,
      response.status,
      path,
      raw,
    );
  }
  return response.text();
}

export const apiClient = {
  get: <TSchema extends z.ZodTypeAny>(
    path: string,
    schema: TSchema,
    signal?: AbortSignal,
  ): Promise<z.infer<TSchema>> => request(path, { schema, signal }),

  getText: (path: string, signal?: AbortSignal): Promise<string> => requestText(path, signal),

  post: <TSchema extends z.ZodTypeAny>(
    path: string,
    schema: TSchema,
    body: unknown,
    signal?: AbortSignal,
  ): Promise<z.infer<TSchema>> => request(path, { schema, method: 'POST', body, signal }),

  // No caller in this app expects a meaningful DELETE response body (a 204), so unlike
  // `get`/`post` this does not take a schema — there is nothing for one to validate.
  delete: (path: string, signal?: AbortSignal): Promise<void> =>
    request(path, { schema: z.void(), method: 'DELETE', signal }),
};
