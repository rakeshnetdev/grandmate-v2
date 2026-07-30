/**
 * The workspace's default middle-panel view (Phase 16a, D-035, D-035 scope decision 3):
 * profile-level analytics + training plan, shown whenever no game is selected — the
 * panel is never empty. Thin wrapper around the existing `analytics` feature.
 */
import { ProfileDashboard } from '@/features/analytics';

interface OverviewTabProps {
  profileId?: string;
}

export function OverviewTab({ profileId }: OverviewTabProps) {
  return <ProfileDashboard profileId={profileId} />;
}
