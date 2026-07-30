import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { CitationList } from './CitationList';

describe('CitationList', () => {
  it('renders nothing when there are no citations', () => {
    const { container } = render(<CitationList citations={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('shows a source count toggle', () => {
    render(<CitationList citations={[{ kind: 'move', ply: 4, san: 'e4' }]} />);
    expect(screen.getByRole('button', { name: 'Show 1 source' })).toBeInTheDocument();
  });

  it('pluralises the count for multiple citations', () => {
    render(
      <CitationList
        citations={[
          { kind: 'move', ply: 4, san: 'e4' },
          { kind: 'opening', eco: 'C50', opening_name: 'Italian Game' },
        ]}
      />,
    );
    expect(screen.getByRole('button', { name: 'Show 2 sources' })).toBeInTheDocument();
  });

  it('expands to show a human-readable description per citation kind on click', async () => {
    const user = userEvent.setup();
    render(
      <CitationList
        citations={[
          { kind: 'move', ply: 4, san: 'e4' },
          { kind: 'evaluation', ply: 4, eval_cp: 25, mate_in: null },
          { kind: 'variation', moves: ['e4', 'e5', 'Nf3'] },
          { kind: 'opening', eco: 'C50', opening_name: 'Italian Game' },
        ]}
      />,
    );

    await user.click(screen.getByRole('button', { name: /Show 4 sources/ }));

    expect(screen.getByText('Move 4: e4')).toBeInTheDocument();
    expect(screen.getByText('Evaluation at ply 4: 25cp')).toBeInTheDocument();
    expect(screen.getByText('Line: e4 e5 Nf3')).toBeInTheDocument();
    expect(screen.getByText('Italian Game (C50)')).toBeInTheDocument();
  });

  it('falls back to the raw kind for an unrecognised citation shape', async () => {
    const user = userEvent.setup();
    render(<CitationList citations={[{ kind: 'mystery' }]} />);

    await user.click(screen.getByRole('button', { name: /Show 1 source/ }));

    expect(screen.getByText('mystery')).toBeInTheDocument();
  });
});
