/**
 * Minimal tab list (Phase 16a, D-035) — a controlled list of buttons with `role="tab"`,
 * matching `PersonaSwitcher`/`WindowSelector`'s existing button-group pattern rather
 * than introducing a new primitive shape. Content switching is the caller's job (just
 * render whichever panel matches `value`) — this component only ever renders the tab
 * strip itself.
 */
import { cn } from '@/shared/lib/utils';

export interface TabItem {
  value: string;
  label: string;
}

interface TabsProps {
  items: TabItem[];
  value: string;
  onChange: (value: string) => void;
  className?: string;
}

export function Tabs({ items, value, onChange, className }: TabsProps) {
  return (
    <div
      role="tablist"
      className={cn(
        'flex gap-1 overflow-x-auto border-b border-border',
        // Below the responsive breakpoint (Phase 16a) tabs scroll horizontally rather
        // than wrapping, so the middle panel never grows taller than its content needs.
        className,
      )}
    >
      {items.map((item) => {
        const selected = item.value === value;
        return (
          <button
            key={item.value}
            type="button"
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(item.value)}
            className={cn(
              'shrink-0 border-b-2 px-3 py-2 text-sm font-medium whitespace-nowrap transition-colors',
              selected
                ? 'border-primary text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground',
            )}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
}
