/**
 * The workspace's "Analysis" tab (Phase 16a, D-035) — thin wrapper around the existing
 * persona report panel, so persona switching/report rendering logic stays owned by the
 * `reports` feature rather than being duplicated here.
 */
import { PersonaReportPanel } from '@/features/reports';

interface AnalysisTabProps {
  gameId: string;
  profileId?: string;
}

export function AnalysisTab({ gameId, profileId }: AnalysisTabProps) {
  return <PersonaReportPanel gameId={gameId} profileId={profileId} />;
}
