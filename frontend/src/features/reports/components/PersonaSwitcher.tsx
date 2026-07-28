/**
 * Self-learner / coach / kid persona toggle (Phase 9, `persona-matrix.md`).
 */
import { Button } from '@/shared/components/ui/button';

import type { PersonaValue } from '../api/reports';

const PERSONAS: { value: PersonaValue; label: string }[] = [
  { value: 'self_learner', label: 'Self-learner' },
  { value: 'coach', label: 'Coach' },
  { value: 'kid', label: 'Kid' },
];

interface PersonaSwitcherProps {
  value: PersonaValue;
  onChange: (persona: PersonaValue) => void;
}

export function PersonaSwitcher({ value, onChange }: PersonaSwitcherProps) {
  return (
    <div className="flex gap-2" role="radiogroup" aria-label="Persona">
      {PERSONAS.map((persona) => (
        <Button
          key={persona.value}
          type="button"
          variant={value === persona.value ? 'default' : 'outline'}
          size="sm"
          aria-pressed={value === persona.value}
          onClick={() => onChange(persona.value)}
        >
          {persona.label}
        </Button>
      ))}
    </div>
  );
}
