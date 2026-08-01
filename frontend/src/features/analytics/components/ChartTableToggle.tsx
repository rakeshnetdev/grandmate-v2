/**
 * Chart ⇄ table switch for a dashboard section.
 *
 * A table view is not optional decoration: a chart encodes some of its information in
 * geometry, and a reader using a screen reader, needing exact figures, or copying numbers
 * out needs the tabular form. Keeping both behind one control means neither is a
 * second-class citizen, and the chart is free to be a chart.
 */
import { useState } from 'react';

import type { ReactNode } from 'react';

interface ChartTableToggleProps {
  chart: ReactNode;
  table: ReactNode;
  /** Names the section in the control's accessible label. */
  label: string;
}

export function ChartTableToggle({ chart, table, label }: ChartTableToggleProps) {
  const [view, setView] = useState<'chart' | 'table'>('chart');

  return (
    <div className="space-y-2">
      <div className="flex justify-end" role="group" aria-label={`${label} view`}>
        <div className="inline-flex overflow-hidden rounded-md border border-border text-xs">
          {(['chart', 'table'] as const).map((option) => (
            <button
              key={option}
              type="button"
              aria-pressed={view === option}
              onClick={() => setView(option)}
              className={
                view === option
                  ? 'bg-accent px-2 py-1 font-medium text-accent-foreground'
                  : 'px-2 py-1 text-muted-foreground hover:text-foreground'
              }
            >
              {option === 'chart' ? 'Chart' : 'Table'}
            </button>
          ))}
        </div>
      </div>
      {view === 'chart' ? chart : table}
    </div>
  );
}
