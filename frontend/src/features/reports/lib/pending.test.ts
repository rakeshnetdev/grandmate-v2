/**
 * `isAnalysisPending` tests. This predicate decides whether the reader sees "still
 * analyzing, sit tight" or "this is broken", so both directions matter: a false negative
 * shows a scary error during the normal post-import wait, and a false positive polls
 * forever against a game that will never produce a report.
 */
import { describe, expect, it } from 'vitest';

import { ApiError } from '@/shared/lib/api-client';

import { analyzingLineFor, isAnalysisPending, ANALYZING_LINES } from './pending';

function apiError(status: number, detail?: string) {
  return new ApiError(`failed with ${status}`, status, '/api/v1/reports/x', { detail });
}

describe('isAnalysisPending', () => {
  it('is true for the "no analysis yet" 404 the reports route returns after import', () => {
    expect(isAnalysisPending(apiError(404, 'No analysis found for this game yet'))).toBe(true);
  });

  it('is false for a missing game, which is a real 404', () => {
    expect(isAnalysisPending(apiError(404, 'Game not found'))).toBe(false);
  });

  it('is false for a server error', () => {
    expect(isAnalysisPending(apiError(500, 'boom'))).toBe(false);
  });

  it('is false for a non-API error, so an unexpected throw is never mistaken for waiting', () => {
    expect(isAnalysisPending(new Error('network down'))).toBe(false);
    expect(isAnalysisPending(undefined)).toBe(false);
  });
});

describe('analyzingLineFor', () => {
  it('always returns one of the known lines', () => {
    expect(ANALYZING_LINES).toContain(analyzingLineFor('game-1'));
  });

  it('is stable for a given game, so the line does not shuffle mid-wait', () => {
    expect(analyzingLineFor('game-abc')).toBe(analyzingLineFor('game-abc'));
  });
});
