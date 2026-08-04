/**
 * The icon-only refresh control used wherever generated content can be produced again.
 *
 * A shared primitive rather than a per-feature button because it appears in three places
 * with the same meaning — the persona report, the game story, and pattern feedback — and
 * in two different states: beside the provenance badge once content has loaded, and beside
 * the error text when it failed to load. That second placement is the reason it lives
 * here: an error branch renders no badge, so it cannot borrow the badge's copy.
 *
 * Icon-only means `aria-label` is the button's only accessible name, so `label` is
 * required rather than optional, and the spin doubles as the progress indicator since
 * there is no text to swap out.
 */
import { RefreshCw } from 'lucide-react';

import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/lib/utils';

interface RegenerateButtonProps {
  onClick: () => void;
  /** Names what is being regenerated ("report", "story", "feedback") so several of these
   * on adjacent tabs do not all announce as a bare "Regenerate". */
  label: string;
  isBusy?: boolean;
  className?: string;
}

export function RegenerateButton({
  onClick,
  label,
  isBusy = false,
  className,
}: RegenerateButtonProps) {
  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      className={cn('h-6 w-6 shrink-0 text-muted-foreground hover:text-foreground', className)}
      disabled={isBusy}
      onClick={onClick}
      aria-label={isBusy ? `Regenerating ${label}…` : `Regenerate ${label}`}
      title={`Regenerate ${label}`}
    >
      <RefreshCw className={cn('h-3.5 w-3.5', isBusy && 'animate-spin')} />
    </Button>
  );
}
