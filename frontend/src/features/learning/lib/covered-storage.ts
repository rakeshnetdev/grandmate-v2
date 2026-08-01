/**
 * Persistence for "already covered" focus items.
 *
 * Stores the item *keys* a reader has moved past, not a round number. A round index
 * would decay into a lie: the ranking is recomputed from analytics on every load, so
 * once new games are analyzed "round 2" no longer names the same three things it did
 * yesterday, and the covered list would silently start describing items the reader never
 * saw. Keys survive re-ranking intact.
 *
 * localStorage rather than the backend: this is per-reader progress through a suggestion
 * list, not analysis truth, and it does not need to follow the account across devices at
 * MVP scope. Moving it server-side later means writing a repository, not rewriting the
 * panel — the shape below (a set of keys per profile) is what a table would hold too.
 *
 * Same storage conventions as `shared/theme/ThemeProvider`: a versioned key, and every
 * read defensive against a browser that denies access (Safari private mode) or a value
 * some other version of this code wrote.
 */

/** Bumping the version retires old values rather than trying to migrate them. */
const STORAGE_PREFIX = 'grandmate.learning.covered.v1';

/** `undefined` profile means the caller's own SELF profile, matching the API convention. */
function storageKey(profileId: string | undefined): string {
  return `${STORAGE_PREFIX}.${profileId ?? 'self'}`;
}

/** Namespaced so an opening and a motif that share a name cannot collide. */
export function openingKey(family: string): string {
  return `opening:${family}`;
}

export function motifKey(name: string): string {
  return `motif:${name}`;
}

export function readCovered(profileId: string | undefined): string[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(storageKey(profileId));
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    // Anything not a string array is treated as absent — a corrupt or stale value must
    // not break the panel that reads it.
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((entry): entry is string => typeof entry === 'string');
  } catch {
    return [];
  }
}

export function writeCovered(profileId: string | undefined, keys: string[]): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(storageKey(profileId), JSON.stringify(keys));
  } catch {
    // Storage denied or full. Losing the record is survivable — the session keeps its
    // in-memory state and the reader simply starts fresh next visit.
  }
}

export function clearCovered(profileId: string | undefined): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.removeItem(storageKey(profileId));
  } catch {
    // Same reasoning as writeCovered.
  }
}
