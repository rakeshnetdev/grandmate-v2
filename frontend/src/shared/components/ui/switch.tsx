/**
 * Toggle switch primitive — hand-rolled for the same reason as `Dialog`: the app carries
 * no Radix dependency, and this is a track with a sliding thumb, not a behaviour worth
 * pulling one in for.
 *
 * `role="switch"` + `aria-checked` rather than a pressed button: a switch takes effect
 * immediately, which is what assistive tech announces for this role, where `aria-pressed`
 * describes a button that has been pushed.
 *
 * The label lives *inside* the control rather than beside it, so it names the switch
 * without a separate `aria-label` to keep in step, and clicking the text toggles as
 * readily as clicking the track — both free from it being one button.
 */
import { cn } from '@/shared/lib/utils';

interface SwitchProps {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  label: string;
  className?: string;
}

export function Switch({ checked, onCheckedChange, label, className }: SwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onCheckedChange(!checked)}
      className={cn(
        'inline-flex items-center gap-2 rounded-md text-sm whitespace-nowrap transition-colors',
        'focus-visible:ring-ring focus-visible:ring-2 focus-visible:outline-none',
        checked ? 'text-foreground' : 'text-muted-foreground hover:text-foreground',
        className,
      )}
    >
      <span
        className={cn(
          'inline-flex h-5 w-9 shrink-0 items-center rounded-full border-2 border-transparent transition-colors',
          checked ? 'bg-primary' : 'bg-input',
        )}
      >
        <span
          className={cn(
            'bg-background pointer-events-none block h-4 w-4 rounded-full shadow-sm transition-transform',
            checked ? 'translate-x-4' : 'translate-x-0',
          )}
        />
      </span>
      {label}
    </button>
  );
}
