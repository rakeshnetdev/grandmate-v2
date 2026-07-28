/**
 * "My games" / "Study games" toggle (Phase 8b, D-021, ADR-0016).
 *
 * `value` is `undefined` for the caller's own SELF profile (the default every route
 * already falls back to server-side) — only the study profile's id is ever passed
 * explicitly, so a page that never touches this component behaves exactly as it did
 * before Phase 8b.
 */
import { Button } from '@/shared/components/ui/button';

import { useProfiles } from '../hooks/useProfiles';

interface ProfileToggleProps {
  value: string | undefined;
  onChange: (profileId: string | undefined) => void;
}

export function ProfileToggle({ value, onChange }: ProfileToggleProps) {
  const { data: profiles } = useProfiles();
  const study = profiles?.find((p) => p.kind === 'opponent');

  if (!study) {
    return null;
  }

  return (
    <div className="flex gap-2" role="radiogroup" aria-label="Profile">
      <Button
        type="button"
        variant={value === undefined ? 'default' : 'outline'}
        size="sm"
        aria-pressed={value === undefined}
        onClick={() => onChange(undefined)}
      >
        My games
      </Button>
      <Button
        type="button"
        variant={value === study.id ? 'default' : 'outline'}
        size="sm"
        aria-pressed={value === study.id}
        onClick={() => onChange(study.id)}
      >
        {study.display_name}
      </Button>
    </div>
  );
}
