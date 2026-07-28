/**
 * Persona switcher + the selected persona's report (Phase 9). Composition only — see
 * `PersonaSwitcher`/`ReportView` for the pieces.
 */
import { useState } from 'react';

import type { PersonaValue } from '../api/reports';
import { useGameReport } from '../hooks/useReports';
import { PersonaSwitcher } from './PersonaSwitcher';
import { ReportView } from './ReportView';

interface PersonaReportPanelProps {
  gameId: string;
  /** `undefined` means the caller's own SELF profile (Phase 8b). */
  profileId?: string;
}

export function PersonaReportPanel({ gameId, profileId }: PersonaReportPanelProps) {
  const [persona, setPersona] = useState<PersonaValue>('self_learner');
  const { data: report, isLoading, isError } = useGameReport(gameId, persona, profileId);

  return (
    <div className="space-y-4">
      <PersonaSwitcher value={persona} onChange={setPersona} />

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Generating report…</p>
      ) : isError ? (
        <p className="text-sm text-destructive">Could not load the report.</p>
      ) : report ? (
        <ReportView report={report} />
      ) : null}
    </div>
  );
}
