/**
 * Whether the engine-analysis tabs ("Moves", "Patterns") are on offer, persisted.
 *
 * Off by default: those two tabs are the raw deterministic output — per-ply evaluations
 * and detected motifs — and a reader who came to understand one game shouldn't have to
 * walk past them first. Turning it on is an explicit "show me the engine's working".
 *
 * Stored rather than kept in the URL, on the same reasoning as
 * `useLeftPanelCollapsed`: it is a standing preference about how much detail this reader
 * wants, not a view worth bookmarking or sharing.
 */
import { useState } from 'react';

const STORAGE_KEY = 'grandmate-workspace-show-engine-analysis';

function readStored(): boolean {
  if (typeof window === 'undefined') {
    return false;
  }
  return window.localStorage.getItem(STORAGE_KEY) === 'true';
}

export function useShowEngineAnalysis(): [boolean, () => void] {
  const [shown, setShown] = useState(readStored);

  function toggle() {
    setShown((prev) => {
      const next = !prev;
      window.localStorage.setItem(STORAGE_KEY, String(next));
      return next;
    });
  }

  return [shown, toggle];
}
