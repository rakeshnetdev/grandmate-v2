/**
 * Minimal accessible modal (Phase 16a, D-035) — hand-rolled rather than adding a Radix
 * dependency for one use (the import modal): backdrop click and Escape both close,
 * focus moves into the panel on open, `role="dialog"`/`aria-modal` for assistive tech.
 * Not a general-purpose focus trap — good enough for a single-panel, no-nested-dialog
 * app like this one.
 */
import type { ReactNode } from 'react';
import { useEffect, useRef } from 'react';

import { cn } from '@/shared/lib/utils';

interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  className?: string;
}

export function Dialog({ open, onClose, title, children, className }: DialogProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    panelRef.current?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        onClose();
      }
    }
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [open, onClose]);

  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="Close"
        className="absolute inset-0 bg-background/80 backdrop-blur-sm"
        onClick={onClose}
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        className={cn(
          'relative z-10 max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-lg border border-border bg-card p-6 shadow-lg outline-none',
          className,
        )}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button
            type="button"
            aria-label="Close"
            onClick={onClose}
            className="rounded-md p-1 text-muted-foreground hover:bg-accent hover:text-accent-foreground"
          >
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
