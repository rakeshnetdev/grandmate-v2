import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { ClassificationBadge } from './classification-badge';

describe('ClassificationBadge', () => {
  it('renders the human label for the given classification', () => {
    render(<ClassificationBadge classification="blunder" />);
    expect(screen.getByText('Blunder')).toBeInTheDocument();
  });

  it.each(['best', 'good', 'inaccuracy', 'mistake', 'blunder'] as const)(
    'renders %s without throwing',
    (classification) => {
      render(<ClassificationBadge classification={classification} />);
      expect(screen.getByText(new RegExp(classification, 'i'))).toBeInTheDocument();
    },
  );
});
