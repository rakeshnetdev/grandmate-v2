/**
 * Profile-level "what to work on this week" tab. Thin wrapper around the `learning`
 * feature, same shape as `OverviewTab` — the tab owns placement, the feature owns
 * behaviour.
 */
import { WeeklyFocusPanel } from '@/features/learning';

interface LearningTabProps {
  profileId?: string;
}

export function LearningTab({ profileId }: LearningTabProps) {
  return <WeeklyFocusPanel profileId={profileId} />;
}
