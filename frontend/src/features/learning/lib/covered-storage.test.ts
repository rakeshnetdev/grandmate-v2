/**
 * Covered-item persistence tests. The whole point of this module is that the list
 * survives a reload, so the round trip is the test — plus the defensive reads, because a
 * corrupt value or a browser that denies storage must not take the panel down with it.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';

import { clearCovered, motifKey, openingKey, readCovered, writeCovered } from './covered-storage';

afterEach(() => {
  window.localStorage.clear();
  vi.restoreAllMocks();
});

describe('covered storage', () => {
  it('round-trips covered keys, which is what makes the list survive a reload', () => {
    writeCovered(undefined, [openingKey('Sicilian Defense'), motifKey('fork')]);

    expect(readCovered(undefined)).toEqual(['opening:Sicilian Defense', 'motif:fork']);
  });

  it('keeps profiles separate, so progress belongs to the profile being read', () => {
    writeCovered(undefined, [motifKey('pin')]);
    writeCovered('profile-2', [motifKey('skewer')]);

    expect(readCovered(undefined)).toEqual(['motif:pin']);
    expect(readCovered('profile-2')).toEqual(['motif:skewer']);
  });

  it('namespaces kinds so an opening and a motif of the same name cannot collide', () => {
    expect(openingKey('London System')).not.toBe(motifKey('London System'));
  });

  it('returns empty for an unknown profile', () => {
    expect(readCovered('never-seen')).toEqual([]);
  });

  it('treats a corrupt stored value as absent rather than throwing', () => {
    window.localStorage.setItem('grandmate.learning.covered.v1.self', '{not json');
    expect(readCovered(undefined)).toEqual([]);

    window.localStorage.setItem('grandmate.learning.covered.v1.self', '{"round":2}');
    expect(readCovered(undefined)).toEqual([]);
  });

  it('drops non-string entries from a partially valid value', () => {
    window.localStorage.setItem('grandmate.learning.covered.v1.self', '["motif:fork", 7, null]');
    expect(readCovered(undefined)).toEqual(['motif:fork']);
  });

  it('survives storage being denied, as in private browsing', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError');
    });

    expect(() => writeCovered(undefined, [motifKey('fork')])).not.toThrow();
  });

  it('clears a profile back to nothing covered', () => {
    writeCovered(undefined, [motifKey('fork')]);
    clearCovered(undefined);

    expect(readCovered(undefined)).toEqual([]);
  });
});
