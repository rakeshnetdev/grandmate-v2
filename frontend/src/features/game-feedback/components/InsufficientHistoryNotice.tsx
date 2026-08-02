/**
 * Shown when the player has too few analyzed games behind this one for any comparison to
 * mean anything (Phase 19, D-037).
 *
 * A real state with a real answer, not an error and not an empty view: the feature works,
 * there is simply nothing to compare against yet. It says how far off the player is so the
 * screen reads as progress rather than a wall.
 */
import { History } from 'lucide-react';

interface InsufficientHistoryNoticeProps {
  baselineGames: number;
}

export function InsufficientHistoryNotice({ baselineGames }: InsufficientHistoryNoticeProps) {
  return (
    <div className="flex items-start gap-2.5 text-sm">
      <History className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      <div>
        <p className="font-medium">Not enough history to compare against yet.</p>
        <p className="mt-0.5 text-xs text-muted-foreground">
          {baselineGames === 0
            ? 'This is the earliest analyzed game in your profile. Import a few more and this tab will start spotting what recurs.'
            : `Only ${baselineGames} analyzed ${baselineGames === 1 ? 'game' : 'games'} came before this one — too few to tell a habit from a one-off.`}
        </p>
      </div>
    </div>
  );
}
