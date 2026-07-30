import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { Tabs } from './tabs';

const ITEMS = [
  { value: 'a', label: 'Alpha' },
  { value: 'b', label: 'Beta' },
];

describe('Tabs', () => {
  it('marks the active tab as selected', () => {
    render(<Tabs items={ITEMS} value="a" onChange={() => {}} />);
    expect(screen.getByRole('tab', { name: 'Alpha' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tab', { name: 'Beta' })).toHaveAttribute('aria-selected', 'false');
  });

  it('calls onChange with the clicked tab value', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Tabs items={ITEMS} value="a" onChange={onChange} />);

    await user.click(screen.getByRole('tab', { name: 'Beta' }));

    expect(onChange).toHaveBeenCalledWith('b');
  });
});
