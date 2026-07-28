import { Button } from '@/shared/components/ui/button';

import { WINDOW_OPTIONS } from '../lib/constants';

interface WindowSelectorProps {
  value: number;
  onChange: (window: number) => void;
}

export function WindowSelector({ value, onChange }: WindowSelectorProps) {
  return (
    <div className="flex gap-2" role="radiogroup" aria-label="Window size">
      {WINDOW_OPTIONS.map((size) => (
        <Button
          key={size}
          type="button"
          variant={size === value ? 'default' : 'outline'}
          size="sm"
          aria-pressed={size === value}
          onClick={() => onChange(size)}
        >
          Last {size}
        </Button>
      ))}
    </div>
  );
}
