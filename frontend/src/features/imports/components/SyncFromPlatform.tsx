/**
 * "Sync from Lichess/Chess.com" (Phase 14, D-030/D-031).
 *
 * Two shapes, because the two profiles answer "whose games?" differently:
 *
 * - **Own games** (default): MVP login links exactly one platform per account (whichever
 *   the caller logged in with — there is no route yet to link a second one, see the Phase
 *   14 phase report's known gaps), so this renders one button for `provider`/`username`,
 *   not a picker. Reads both from `useCurrentUser()` rather than a separate "linked
 *   accounts" fetch, since `/api/v1/auth/me` already carries them.
 * - **Study games** (`studyMode`, Phase 16b follow-up): the player being studied has no
 *   linked account and may be on either platform, so both the platform and the username
 *   are entered by hand. The backend needs no target-profile argument — per-game routing
 *   (D-021, ADR-0016) already sends anything that isn't the caller's own play to the
 *   study profile.
 */
import { useState } from 'react';

import { Button } from '@/shared/components/ui/button';
import { ApiError } from '@/shared/lib/api-client';

import type { JobSummary } from '../api/imports';
import { useSyncFromPlatform } from '../hooks/useImports';

const WINDOW_OPTIONS = [10, 30, 60] as const;

type Provider = 'lichess' | 'chesscom';

const PROVIDER_LABEL: Record<Provider, string> = {
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
  provider: Provider;
  username: string;
  /** Ask for an arbitrary player's platform + username instead of syncing the caller's
   * own linked account. */
  studyMode?: boolean;
  onSynced?: (job: JobSummary) => void;
}

function WindowSelect({
  value,
  onChange,
  disabled,
}: {
  value: number;
  onChange: (value: number) => void;
  disabled: boolean;
}) {
  return (
    <>
      <label htmlFor="sync-window" className="text-sm text-muted-foreground">
        Last
      </label>
      <select
        id="sync-window"
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        disabled={disabled}
        className="h-9 rounded-md border border-input bg-background px-2 text-sm"
      >
        {WINDOW_OPTIONS.map((size) => (
          <option key={size} value={size}>
            {size} games
          </option>
        ))}
      </select>
    </>
  );
}

export function SyncFromPlatform({
  provider,
  username,
  studyMode = false,
  onSynced,
}: SyncFromPlatformProps) {
  const [gameWindow, setGameWindow] = useState<number>(WINDOW_OPTIONS[0]);
  const [studyProvider, setStudyProvider] = useState<Provider>(provider);
  const [studyUsername, setStudyUsername] = useState('');
  const sync = useSyncFromPlatform();

  const trimmedStudyUsername = studyUsername.trim();

  function handleStudySubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!trimmedStudyUsername) {
      return;
    }
    sync.mutate(
      { provider: studyProvider, window: gameWindow, username: trimmedStudyUsername },
      { onSuccess: (job) => onSynced?.(job) },
    );
  }

  if (studyMode) {
    return (
      <form onSubmit={handleStudySubmit} className="space-y-3">
        <p className="text-sm text-muted-foreground">
          Import another player's games to study. Their games stay in Study games, separate from
          your own.
        </p>
        <div className="flex flex-wrap items-end gap-3">
          <div className="space-y-1">
            <label htmlFor="study-provider" className="block text-sm text-muted-foreground">
              Platform
            </label>
            <select
              id="study-provider"
              value={studyProvider}
              onChange={(event) => setStudyProvider(event.target.value as Provider)}
              disabled={sync.isPending}
              className="h-9 rounded-md border border-input bg-background px-2 text-sm"
            >
              {(Object.keys(PROVIDER_LABEL) as Provider[]).map((value) => (
                <option key={value} value={value}>
                  {PROVIDER_LABEL[value]}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <label htmlFor="study-username" className="block text-sm text-muted-foreground">
              Username
            </label>
            <input
              id="study-username"
              type="text"
              value={studyUsername}
              onChange={(event) => setStudyUsername(event.target.value)}
              disabled={sync.isPending}
              placeholder={
                studyProvider === 'lichess' ? 'e.g. DrNykterstein' : 'e.g. MagnusCarlsen'
              }
              autoComplete="off"
              spellCheck={false}
              className="h-9 w-56 rounded-md border border-input bg-background px-2 text-sm"
            />
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <WindowSelect value={gameWindow} onChange={setGameWindow} disabled={sync.isPending} />
          <Button
            type="submit"
            variant="secondary"
            disabled={sync.isPending || !trimmedStudyUsername}
          >
            {sync.isPending ? 'Starting import…' : 'Import games'}
          </Button>
        </div>
        {sync.isError && (
          <p className="text-sm text-destructive">{describeSyncError(sync.error)}</p>
        )}
      </form>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      <WindowSelect value={gameWindow} onChange={setGameWindow} disabled={sync.isPending} />
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
