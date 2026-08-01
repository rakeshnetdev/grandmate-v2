/**
 * Telling "not ready yet" apart from "actually broken".
 *
 * A report is generated from a completed engine analysis. Analysis runs as a background
 * job after import, so for the first seconds-to-minutes of a game's life the report
 * endpoint answers 404 "No analysis found for this game yet" (`api/routes/reports.py`).
 * That is the normal path, not a failure — but it arrives on the wire looking exactly
 * like a real 404, which is why the UI used to report both as "Could not load the
 * report."
 *
 * Matching on the server's detail string is admittedly brittle. The robust fix is a
 * dedicated status (409, or a `status: "pending"` body) from the reports route; this
 * keeps the change to the frontend until that contract change is worth making. The
 * fallback is safe in the meantime: an unrecognised 404 is treated as a real error, so a
 * reworded message degrades to today's behaviour rather than spinning forever.
 */
import { ApiError } from '@/shared/lib/api-client';

const NOT_ANALYZED_DETAIL = 'no analysis found';

/** Whether this error means "the engine has not finished with this game yet". */
export function isAnalysisPending(error: unknown): boolean {
  if (!(error instanceof ApiError) || error.status !== 404) {
    return false;
  }
  const detail = (error.body as { detail?: unknown } | undefined)?.detail;
  return typeof detail === 'string' && detail.toLowerCase().includes(NOT_ANALYZED_DETAIL);
}

/**
 * Lines shown while the engine works. Rotating rather than fixed: this screen can be up
 * for a minute or more on a fresh import, and a single line starts to read like the page
 * has frozen.
 *
 * They are cocky about the engine, never about the player — the reader is about to be
 * told what they got wrong, and the wait is not the moment to start needling them.
 */
export const ANALYZING_LINES = [
  'Stockfish is going through your game. Every move. No mercy.',
  'Counting the moment it all went wrong. Usually there is exactly one.',
  'Twelve plies deep and still finding things.',
  'The engine has no opinions, only evaluations. Getting them now.',
  'Replaying your game at a depth you did not have time for.',
];

/** Deterministic per-game pick, so a re-render does not shuffle the line mid-wait. */
export function analyzingLineFor(seed: string): string {
  let hash = 0;
  for (let i = 0; i < seed.length; i += 1) {
    hash = (hash * 31 + seed.charCodeAt(i)) | 0;
  }
  return ANALYZING_LINES[Math.abs(hash) % ANALYZING_LINES.length] as string;
}
