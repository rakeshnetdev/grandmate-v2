/**
 * Displays backend connectivity.
 *
 * Presentational: it renders whatever the hook gives it and makes no network calls of
 * its own. The three states are handled explicitly rather than collapsed, because
 * "loading" and "backend unreachable" mean very different things to someone setting the
 * project up for the first time.
 */
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/shared/components/ui/card';

import { useHealth } from '../hooks/useHealth';

export function BackendStatusCard() {
  const { data, isPending, isError } = useHealth();

  return (
    <Card>
      <CardHeader>
        <CardTitle>Backend</CardTitle>
        <CardDescription>Connectivity to the GrandMate API</CardDescription>
      </CardHeader>
      <CardContent>
        {isPending && <p className="text-sm text-muted-foreground">Checking…</p>}

        {isError && (
          <p className="text-sm text-destructive">
            Unreachable. Start it with{' '}
            <code className="font-mono">uv run uvicorn app.main:app</code> in{' '}
            <code className="font-mono">backend/</code>.
          </p>
        )}

        {data && (
          <dl className="space-y-1 text-sm">
            <div className="flex gap-2">
              <dt className="text-muted-foreground">Service</dt>
              <dd className="font-medium">{data.service}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="text-muted-foreground">Version</dt>
              <dd className="font-medium">{data.version}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="text-muted-foreground">Status</dt>
              <dd className="font-medium text-primary">{data.status}</dd>
            </div>
          </dl>
        )}
      </CardContent>
    </Card>
  );
}
