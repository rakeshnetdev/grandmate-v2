import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { Dialog } from './dialog';

describe('Dialog', () => {
  it('renders nothing when closed', () => {
    render(
      <Dialog open={false} onClose={() => {}} title="Test">
        content
      </Dialog>,
    );
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('renders its title and children when open', () => {
    render(
      <Dialog open onClose={() => {}} title="Import games">
        <p>Body content</p>
      </Dialog>,
    );
    expect(screen.getByRole('dialog', { name: 'Import games' })).toBeInTheDocument();
    expect(screen.getByText('Body content')).toBeInTheDocument();
  });

  it('calls onClose when the backdrop is clicked', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(
      <Dialog open onClose={onClose} title="Test">
        content
      </Dialog>,
    );

    const [backdropButton] = screen.getAllByRole('button', { name: 'Close' });
    expect(backdropButton).toBeDefined();
    await user.click(backdropButton as HTMLElement);

    expect(onClose).toHaveBeenCalled();
  });

  it('calls onClose on Escape', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(
      <Dialog open onClose={onClose} title="Test">
        content
      </Dialog>,
    );

    await user.keyboard('{Escape}');

    expect(onClose).toHaveBeenCalled();
  });
});
