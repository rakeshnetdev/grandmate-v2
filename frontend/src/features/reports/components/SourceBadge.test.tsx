/**
 * `SourceBadge` tests: the provenance label, and the regenerate control beside it.
 *
 * Tested here once rather than in each of `ReportView`/`StoryView`/the pattern-feedback
 * tab, because the badge is now the single shared implementation those three render.
 */
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { SourceBadge } from './SourceBadge';

describe('SourceBadge', () => {
  it('names the provenance of the write-up', () => {
    const { rerender } = render(<SourceBadge source="llm" />);
    expect(screen.getByText('AI-generated')).toBeInTheDocument();

    // A fallback report is not an error, but the reader is told it is not LLM prose.
    rerender(<SourceBadge source="fallback" />);
    expect(screen.getByText('Deterministic summary')).toBeInTheDocument();
  });

  it('offers no regenerate control when the caller supplies no handler', () => {
    render(<SourceBadge source="llm" />);

    expect(screen.queryByRole('button', { name: /regenerate/i })).not.toBeInTheDocument();
  });

  it('regenerates on request, naming what it regenerates', async () => {
    const onRegenerate = vi.fn();
    render(<SourceBadge source="llm" label="story" onRegenerate={onRegenerate} />);

    // Icon-only, so `aria-label` is the button's only accessible name — and it is
    // qualified ("story", not a bare "Regenerate") because adjacent tabs each have one.
    await userEvent.click(screen.getByRole('button', { name: 'Regenerate story' }));

    expect(onRegenerate).toHaveBeenCalledOnce();
  });

  it('disables the control while a regeneration is in flight', () => {
    // Each press spends an LLM call, so a second one must not be reachable mid-flight.
    render(<SourceBadge source="llm" label="report" onRegenerate={vi.fn()} isRegenerating />);

    expect(screen.getByRole('button', { name: 'Regenerating report…' })).toBeDisabled();
  });
});
