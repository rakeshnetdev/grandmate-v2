/**
 * The reader's progress through the focus list, persisted across reloads.
 *
 * Owns the covered-key set and the two ways it changes: "give me next" (mark the current
 * items covered) and "start over" (forget everything). Selection stays a pure function
 * over analytics — see `lib/selection.ts` — so this hook is only about progress, not
 * about what is worth learning.
 */
import { useCallback, useEffect, useState } from 'react';

import { clearCovered, readCovered, writeCovered } from '../lib/covered-storage';

export function useCoveredFocus(profileId: string | undefined) {
  // Lazily initialised from storage so the first paint already has the right list
  // rather than flashing an empty "Already covered" section.
  const [covered, setCovered] = useState<Set<string>>(() => new Set(readCovered(profileId)));

  // Switching profiles switches progress: the covered list belongs to the profile being
  // read, not to the browser tab.
  useEffect(() => {
    setCovered(new Set(readCovered(profileId)));
  }, [profileId]);

  const markCovered = useCallback(
    (keys: string[]) => {
      setCovered((previous) => {
        const next = new Set(previous);
        for (const key of keys) next.add(key);
        writeCovered(profileId, [...next]);
        return next;
      });
    },
    [profileId],
  );

  const reset = useCallback(() => {
    clearCovered(profileId);
    setCovered(new Set());
  }, [profileId]);

  return { covered, markCovered, reset };
}
