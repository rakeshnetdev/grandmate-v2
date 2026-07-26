import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { Button } from './button';

describe('Button', () => {
  it('renders its children', () => {
    render(<Button>Analyse</Button>);

    expect(screen.getByRole('button', { name: 'Analyse' })).toBeInTheDocument();
  });

  it('calls the click handler', async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Go</Button>);

    await userEvent.click(screen.getByRole('button'));

    expect(onClick).toHaveBeenCalledOnce();
  });

  it('does not fire when disabled', async () => {
    const onClick = vi.fn();
    render(
      <Button disabled onClick={onClick}>
        Go
      </Button>,
    );

    await userEvent.click(screen.getByRole('button'));

    expect(onClick).not.toHaveBeenCalled();
  });

  it('applies variant classes', () => {
    render(<Button variant="destructive">Delete</Button>);

    expect(screen.getByRole('button')).toHaveClass('bg-destructive');
  });

  it('lets a caller override conflicting classes', () => {
    // This is the reason cn() uses twMerge: the caller's class must win.
    render(<Button className="bg-accent">Custom</Button>);

    const button = screen.getByRole('button');
    expect(button).toHaveClass('bg-accent');
    expect(button).not.toHaveClass('bg-primary');
  });
});
