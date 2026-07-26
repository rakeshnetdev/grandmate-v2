/**
 * API client tests.
 *
 * The behaviour that matters is schema validation at the boundary: a backend that
 * changes shape must fail loudly here rather than silently rendering `undefined` deep in
 * the component tree.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { z } from 'zod';

import { ApiError, ApiSchemaError, apiClient } from './api-client';

const schema = z.object({ status: z.string(), count: z.number() });

function mockFetch(body: unknown, ok = true, status = 200) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok,
    status,
    json: () => Promise.resolve(body),
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('apiClient.get', () => {
  it('returns parsed data on success', async () => {
    mockFetch({ status: 'ok', count: 3 });

    await expect(apiClient.get('/thing', schema)).resolves.toEqual({ status: 'ok', count: 3 });
  });

  it('prefixes the configured base URL', async () => {
    const fetchMock = mockFetch({ status: 'ok', count: 1 });

    await apiClient.get('/thing', schema);

    expect(fetchMock).toHaveBeenCalledWith('http://localhost:8000/thing', expect.anything());
  });

  it('throws ApiError with the status code on a non-2xx response', async () => {
    mockFetch({ detail: 'nope' }, false, 503);

    const error = await apiClient.get('/thing', schema).catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(503);
    expect((error as ApiError).path).toBe('/thing');
  });

  it('throws ApiSchemaError when the response shape is wrong', async () => {
    mockFetch({ status: 'ok', count: 'three' });

    const error = await apiClient.get('/thing', schema).catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiSchemaError);
    expect((error as ApiSchemaError).issues.length).toBeGreaterThan(0);
  });

  it('sends credentials so backend-issued session cookies travel', async () => {
    const fetchMock = mockFetch({ status: 'ok', count: 1 });

    await apiClient.get('/thing', schema);

    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({ credentials: 'include' });
  });
});

describe('apiClient.post', () => {
  it('serialises the body and sets the content type', async () => {
    const fetchMock = mockFetch({ status: 'ok', count: 1 });

    await apiClient.post('/thing', schema, { name: 'x' });

    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({
      method: 'POST',
      body: JSON.stringify({ name: 'x' }),
      headers: { 'Content-Type': 'application/json' },
    });
  });
});
