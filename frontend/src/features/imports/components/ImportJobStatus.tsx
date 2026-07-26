/**
 * Visible status for one import job: counts plus, when present, the per-game reasons a
 * submission wasn't fully imported. Polls automatically via `useImportJob` until the job
 * reaches a terminal status.
 */
import { cn } from '@/shared/lib/utils';

import type { JobSummary } from '../api/imports';
import { useImportJob } from '../hooks/useImports';

const STATUS_LABEL: Record<JobSummary['status'], string> = {
  pending: 'Queued',
  processing: 'Importing…',
  done: 'Done',
  failed: 'Failed',
};

const STATUS_CLASS: Record<JobSummary['status'], string> = {
  pending: 'text-muted-foreground',
  processing: 'text-muted-foreground',
  done: 'text-green-600 dark:text-green-500',
  failed: 'text-destructive',
};

interface ImportJobStatusProps {
  jobId: string;
}

export function ImportJobStatus({ jobId }: ImportJobStatusProps) {
  const { data: job, isLoading } = useImportJob(jobId);

  if (isLoading || !job) {
    return <p className="text-sm text-muted-foreground">Loading job status…</p>;
  }

  return (
    <div className="space-y-2 rounded-md border border-border p-4">
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <span className={cn('text-sm font-medium', STATUS_CLASS[job.status])}>
          {STATUS_LABEL[job.status]}
        </span>
        <span className="text-xs text-muted-foreground">
          {job.progress.imported} imported · {job.progress.duplicates} duplicate
          {job.progress.duplicates === 1 ? '' : 's'} · {job.progress.rejected.length} rejected
        </span>
      </div>

      {job.error && (
        <p className="text-sm text-destructive">
          {typeof job.error.reason === 'string' ? job.error.reason : 'Import failed.'}
        </p>
      )}

      {job.progress.rejected.length > 0 && (
        <ul className="space-y-1 text-xs text-muted-foreground">
          {job.progress.rejected.map((rejection, index) => (
            <li key={`${rejection.source}-${rejection.index}-${index}`}>
              <span className="font-medium">{rejection.source}</span> (game {rejection.index + 1}):{' '}
              {rejection.reason.replaceAll('_', ' ')} — {rejection.detail}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
