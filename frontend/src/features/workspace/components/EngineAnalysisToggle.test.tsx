import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { EngineAnalysisToggle } from './EngineAnalysisToggle';

describe('EngineAnalysisToggle', () => {
  it('reads as unchecked when engine analysis is hidden', () => {
    render(<EngineAnalysisToggle shown={false} onToggle={() => {}} />);

    expect(screen.getByRole('switch', { name: 'Show engine analysis' })).toHaveAttribute(
      'aria-checked',
      'false',
    );
  });

  it('reads as checked when engine analysis is shown', () => {
    render(<EngineAnalysisToggle shown onToggle={() => {}} />);

    expect(screen.getByRole('switch', { name: 'Show engine analysis' })).toHaveAttribute(
      'aria-checked',
      'true',
    );
  });

  it('calls onToggle when clicked', async () => {
    const user = userEvent.setup();
    const onToggle = vi.fn();
    render(<EngineAnalysisToggle shown={false} onToggle={onToggle} />);

    await user.click(screen.getByRole('switch', { name: 'Show engine analysis' }));

    expect(onToggle).toHaveBeenCalledOnce();
  });
});
