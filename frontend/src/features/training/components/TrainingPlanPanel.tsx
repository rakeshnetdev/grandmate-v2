/**
 * On-demand training-plan generator (Phase 15, D-032): a persona picker, an explicit
 * "Generate" action, and the resulting plan. Explicit rather than auto-firing like
 * `ProfileDashboard`'s analytics — see `useGenerateTrainingPlan`'s docstring for why a
 * training plan must never be a side effect of the page simply rendering.
 *
 * `windowSize` is a prop, not a second selector: a plan is built from the same windowed
 * analytics snapshot the dashboard above it is already showing, so a plan-specific
 * window control would be a redundant, confusing second control for the same setting
 * rather than a real independent choice.
 */
import { useState } from 'react';

import { Button } from '@/shared/components/ui/button';

import { PersonaSwitcher, type PersonaValue } from '@/features/reports';

import { useGenerateTrainingPlan } from '../hooks/useTraining';
import { TrainingPlanView } from './TrainingPlanView';

interface TrainingPlanPanelProps {
  /** `undefined` means the caller's own SELF profile (Phase 8b). */
  profileId?: string;
  /** The analytics window this plan is built from — mirrors the dashboard's own
   * current window selection (see the module docstring for why). */
  windowSize: number;
}

export function TrainingPlanPanel({ profileId, windowSize }: TrainingPlanPanelProps) {
  const [persona, setPersona] = useState<PersonaValue>('self_learner');
  const { mutate, data: plan, isPending, isError } = useGenerateTrainingPlan(profileId);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <PersonaSwitcher value={persona} onChange={setPersona} />
        <Button
          type="button"
          size="sm"
          disabled={isPending}
          onClick={() => mutate({ windowSize, persona })}
        >
          {isPending ? 'Generating…' : plan ? 'Regenerate' : 'Generate training plan'}
        </Button>
      </div>

      {isError && <p className="text-sm text-destructive">Could not generate a plan.</p>}
      {plan && <TrainingPlanView plan={plan} />}
    </div>
  );
}
