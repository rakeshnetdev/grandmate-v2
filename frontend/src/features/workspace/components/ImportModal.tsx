/**
 * Import games modal (Phase 16a, D-035) — opened from the left game-list panel,
 * replacing the standalone imports page. Two tabs, reusing the exact same components
 * and API calls `ImportsPage` used: `SyncFromPlatform` and `UploadForm`. On a
 * successful submission, shows the job's live status (`ImportJobStatus`, already polls
 * to completion) in place rather than closing immediately — an import is a background
 * job, so closing on submit would hide whether it actually succeeded.
 */
import { useState } from 'react';

import { useCurrentUser } from '@/features/auth';
import { ImportJobStatus, SyncFromPlatform, UploadForm } from '@/features/imports';
import { Button } from '@/shared/components/ui/button';
import { Dialog } from '@/shared/components/ui/dialog';
import { Tabs } from '@/shared/components/ui/tabs';

const IMPORT_TABS = [
  { value: 'sync', label: 'Sync from platform' },
  { value: 'upload', label: 'Upload or paste' },
];

interface ImportModalProps {
  open: boolean;
  onClose: () => void;
  /** The workspace's active profile — `undefined` is the caller's own SELF profile, any
   * id is the study profile (see `ProfileToggle`). Study mode asks for the studied
   * player's platform + username instead of syncing the caller's own linked account. */
  profileId?: string;
}

export function ImportModal({ open, onClose, profileId }: ImportModalProps) {
  const studyMode = profileId !== undefined;
  const { data: user } = useCurrentUser();
  const [tab, setTab] = useState<'sync' | 'upload'>('sync');
  const [jobId, setJobId] = useState<string>();

  function handleClose() {
    setJobId(undefined);
    onClose();
  }

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      title={studyMode ? 'Import study games' : 'Import games'}
    >
      {!user ? (
        <p className="text-sm text-muted-foreground">
          Log in with Lichess or Chess.com to import games.
        </p>
      ) : jobId ? (
        <div className="space-y-4">
          <ImportJobStatus jobId={jobId} />
          <Button type="button" variant="secondary" onClick={handleClose}>
            Done
          </Button>
        </div>
      ) : (
        <div className="space-y-4">
          <Tabs items={IMPORT_TABS} value={tab} onChange={(value) => setTab(value as typeof tab)} />
          {tab === 'sync' ? (
            <SyncFromPlatform
              provider={user.provider}
              username={user.username}
              studyMode={studyMode}
              onSynced={(job) => setJobId(job.id)}
            />
          ) : (
            <UploadForm onImported={(job) => setJobId(job.id)} />
          )}
        </div>
      )}
    </Dialog>
  );
}
