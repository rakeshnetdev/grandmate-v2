/**
 * Game ingestion: paste PGN, upload files, and see recent import jobs with their status.
 *
 * A newly created job appears at the top of "Recent imports" — `useCreateImport`
 * invalidates the job list on success, so there is no separate "just imported" section
 * duplicating what the list already shows.
 */
import { useCurrentUser } from '@/features/auth';
import { ImportJobStatus, UploadForm, useImportJobs } from '@/features/imports';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/shared/components/ui/card';

export function ImportsPage() {
  const { data: user } = useCurrentUser();
  const { data: jobs } = useImportJobs({ enabled: Boolean(user) });

  if (!user) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Import games</CardTitle>
          <CardDescription>Log in with Lichess or Chess.com to import games</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Import games</h1>
        <p className="mt-1 text-muted-foreground">
          Paste a PGN, or upload one or more PGN files — a file may contain a single game or many.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Upload</CardTitle>
          <CardDescription>Games are matched against what you've already imported</CardDescription>
        </CardHeader>
        <CardContent>
          <UploadForm />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent imports</CardTitle>
        </CardHeader>
        <CardContent>
          {jobs && jobs.length > 0 ? (
            <ul className="space-y-2">
              {jobs.map((job) => (
                <li key={job.id}>
                  <ImportJobStatus jobId={job.id} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">No imports yet.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
