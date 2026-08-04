/**
 * Persona switcher + the selected persona's report (Phase 9). Composition only — see
 * `PersonaSwitcher`/`ReportView` for the pieces.
 */
import { useState } from 'react';

import { RegenerateButton } from '@/shared/components/ui/regenerate-button';

import type { PersonaValue } from '../api/reports';
import { useGameReport, useRegenerateGameReport } from '../hooks/useReports';
import { isAnalysisPending } from '../lib/pending';
import { AnalyzingNotice } from './AnalyzingNotice';
import { PersonaSwitcher } from './PersonaSwitcher';
import { ReportView } from './ReportView';

interface PersonaReportPanelProps {
  gameId: string;
  /** `undefined` means the caller's own SELF profile (Phase 8b). */
  profileId?: string;
}

export function PersonaReportPanel({ gameId, profileId }: PersonaReportPanelProps) {
  const [persona, setPersona] = useState<PersonaValue>('self_learner');
  const {
    data: report,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useGameReport(gameId, persona, profileId);
  // Keyed by persona, so regenerating the coach report cannot overwrite the kid one.
  const regenerate = useRegenerateGameReport(gameId, persona, profileId);

  // "The engine has not got here yet" is the normal state right after an import, not a
  // failure — it only looked like one because both arrive as a 404.
  const pending = isAnalysisPending(error);

  return (
    <div className="space-y-4">
      <PersonaSwitcher value={persona} onChange={setPersona} />

      {regenerate.isError && (
        <p className="text-sm text-destructive">
          Could not regenerate the report. The one below is the previous version.
        </p>
      )}

      {pending ? (
        <AnalyzingNotice gameId={gameId} />
      ) : isLoading ? (
        <p className="text-sm text-muted-foreground">Generating report…</p>
      ) : isError ? (
        // A failed load leaves no report to show, so there is no badge to hang the
        // refresh control off — it goes here instead, or the tab is a dead end. This one
        // refetches rather than regenerating: the request never succeeded, so there is no
        // stored version to discard, and a plain retry re-runs generation server-side
        // anyway whenever no valid report exists.
        <div className="flex items-start justify-between gap-3">
          <p className="text-sm text-destructive">
            Could not load the report. The game may have failed to analyze — try re-importing it.
          </p>
          <RegenerateButton
            onClick={() => void refetch()}
            label="report"
            isBusy={isFetching}
            className="text-destructive hover:text-destructive"
          />
        </div>
      ) : report ? (
        <ReportView
          report={report}
          onRegenerate={() => regenerate.mutate()}
          isRegenerating={regenerate.isPending}
        />
      ) : null}
    </div>
  );
}
