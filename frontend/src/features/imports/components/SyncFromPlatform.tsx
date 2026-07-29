/**
 * "Sync from Lichess/Chess.com" button (Phase 14, D-030/D-031).
 *
 * MVP login links exactly one platform per account (whichever the caller logged in
 * with — there is no route yet to link a second one, see the Phase 14 phase report's
 * known gaps), so this renders one button for `provider`/`username`, not a picker.
 * Reads `provider`/`username` from `useCurrentUser()` rather than fetching a separate
 * "linked accounts" list, since `/api/v1/auth/me` already carries both.
 */
import { useState } from 'react';

import { Button } from '@/shared/components/ui/button';
import { ApiError } from '@/shared/lib/api-client';

import type { JobSummary } from '../api/imports';
import { useSyncFromPlatform } from '../hooks/useImports';

const WINDOW_OPTIONS = [10, 30, 60] as const;

const PROVIDER_LABEL: Record<'lichess' | 'chesscom', string> = {
  lichess: 'Lichess',
  chesscom: 'Chess.com',
};

function describeSyncError(error: unknown): string {
  if (error instanceof ApiError) {
    const detail = (error.body as { detail?: string } | undefined)?.detail;
    if (error.status === 404) {
      return detail ?? 'No linked account found for that platform.';
    }
    if (error.status === 422) {
      return detail ?? 'That sync request could not be processed.';
    }
  }
  return 'Something went wrong. Please try again.';
}

interface SyncFromPlatformProps {
  provider: 'lichess' | 'chesscom';
  username: string;
  onSynced?: (job: JobSummary) => void;
}

export function SyncFromPlatform({ provider, username, onSynced }: SyncFromPlatformProps) {
  const [gameWindow, setGameWindow] = useState<number>(WINDOW_OPTIONS[0]);
  const sync = useSyncFromPlatform();

  return (
    <div className="flex flex-wrap items-center gap-3">
      <label htmlFor="sync-window" className="text-sm text-muted-foreground">
        Last
      </label>
      <select
        id="sync-window"
        value={gameWindow}
        onChange={(event) => setGameWindow(Number(event.target.value))}
        disabled={sync.isPending}
        className="h-9 rounded-md border border-input bg-background px-2 text-sm"
      >
        {WINDOW_OPTIONS.map((size) => (
          <option key={size} value={size}>
            {size} games
          </option>
        ))}
      </select>
      <Button
        variant="secondary"
        disabled={sync.isPending}
        onClick={() =>
          sync.mutate({ provider, window: gameWindow }, { onSuccess: (job) => onSynced?.(job) })
        }
      >
        {sync.isPending ? 'Starting sync…' : `Sync from ${PROVIDER_LABEL[provider]} (${username})`}
      </Button>
      {sync.isError && (
        <p className="w-full text-sm text-destructive">{describeSyncError(sync.error)}</p>
      )}
    </div>
  );
}
