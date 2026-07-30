/**
 * Left-panel collapsed state, persisted (Phase 16a) — same reasoning as the theme
 * toggle: a reader who collapses the game list to focus on analysis shouldn't have to
 * redo it on every visit.
 */
import { useState } from 'react';

const STORAGE_KEY = 'grandmate-workspace-left-collapsed';

function readStored(): boolean {
  if (typeof window === 'undefined') {
    return false;
  }
  return window.localStorage.getItem(STORAGE_KEY) === 'true';
}

export function useLeftPanelCollapsed(): [boolean, () => void] {
  const [collapsed, setCollapsed] = useState(readStored);

  function toggle() {
    setCollapsed((prev) => {
      const next = !prev;
      window.localStorage.setItem(STORAGE_KEY, String(next));
      return next;
    });
  }

  return [collapsed, toggle];
}
