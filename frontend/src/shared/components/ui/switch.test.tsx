import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { Switch } from './switch';

describe('Switch', () => {
  it('exposes its state through role and aria-checked', () => {
    const { rerender } = render(
      <Switch checked={false} onCheckedChange={() => {}} label="Show detail" />,
    );

    expect(screen.getByRole('switch', { name: 'Show detail' })).toHaveAttribute(
      'aria-checked',
      'false',
    );

    rerender(<Switch checked onCheckedChange={() => {}} label="Show detail" />);

    expect(screen.getByRole('switch', { name: 'Show detail' })).toHaveAttribute(
      'aria-checked',
      'true',
    );
  });

  it('reports the flipped value when clicked', async () => {
    const user = userEvent.setup();
    const onCheckedChange = vi.fn();
    render(<Switch checked={false} onCheckedChange={onCheckedChange} label="Show detail" />);

    await user.click(screen.getByRole('switch', { name: 'Show detail' }));

    expect(onCheckedChange).toHaveBeenCalledWith(true);
  });

  it('is operable from the keyboard, being a real button', async () => {
    const user = userEvent.setup();
    const onCheckedChange = vi.fn();
    render(<Switch checked onCheckedChange={onCheckedChange} label="Show detail" />);

    await user.tab();
    await user.keyboard('{Enter}');

    expect(onCheckedChange).toHaveBeenCalledWith(false);
  });
});
