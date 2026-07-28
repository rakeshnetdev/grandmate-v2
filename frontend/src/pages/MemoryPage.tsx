/**
 * Memory audit page (Phase 11, ADR-0005). `profile` follows the same self/study-profile
 * URL convention as `DashboardPage`/`ChatPage` (Phase 8b).
 */
import { useSearchParams } from 'react-router-dom';

import { MemoryPanel } from '@/features/memory';
import { Card, CardContent } from '@/shared/components/ui/card';

export function MemoryPage() {
  const [searchParams] = useSearchParams();
  const profileId = searchParams.get('profile') ?? undefined;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">What GrandMate remembers</h1>
        <p className="mt-1 text-muted-foreground">
          Durable preferences and goals picked up from chat. Anything here can be forgotten.
        </p>
      </div>

      <Card>
        <CardContent className="pt-6">
          <MemoryPanel profileId={profileId} />
        </CardContent>
      </Card>
    </div>
  );
}
