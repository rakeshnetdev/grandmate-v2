/**
 * `Prose` tests: markdown structure renders as real HTML (not literal `**`/`-`
 * characters), and chess-notation/keyword highlighting wraps matched tokens.
 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Prose } from './prose';

describe('Prose', () => {
  it('renders bold markdown as a real strong element, not literal asterisks', () => {
    render(<Prose>{'This move was **a blunder**.'}</Prose>);
    const strong = screen.getByText('a', { exact: false, selector: 'strong' });
    expect(strong.textContent).toContain('a');
    expect(screen.queryByText(/\*\*/)).not.toBeInTheDocument();
  });

  it('renders a markdown bullet list as real list items', () => {
    render(<Prose>{'- First point\n- Second point'}</Prose>);
    expect(screen.getAllByRole('listitem')).toHaveLength(2);
    expect(screen.queryByText(/^- /)).not.toBeInTheDocument();
  });

  it('renders a paragraph with no markdown syntax as plain text', () => {
    render(<Prose>{'Summarise how this game went for me.'}</Prose>);
    expect(screen.getByText('Summarise how this game went for me.')).toBeInTheDocument();
  });

  it('highlights a SAN move token in prose', () => {
    render(<Prose>{'Why was Nf3 played on move 3?'}</Prose>);
    expect(screen.getByText('Nf3')).toBeInTheDocument();
  });

  it('highlights castling notation', () => {
    render(<Prose>{'Castling with O-O secures the king.'}</Prose>);
    expect(screen.getByText('O-O')).toBeInTheDocument();
  });

  it('highlights the word "blunder" as a keyword', () => {
    render(<Prose>{'That was a serious blunder in the middlegame.'}</Prose>);
    expect(screen.getByText('blunder')).toBeInTheDocument();
  });

  it('does not false-positive on ordinary words shaped like nothing chess-related', () => {
    render(<Prose>{'Take your time and stay calm.'}</Prose>);
    // Sanity: renders without throwing and preserves the plain sentence.
    expect(screen.getByText(/Take your time and stay calm\.?/)).toBeInTheDocument();
  });

  it('inline mode does not wrap a single-line finding in a block-level <p>', () => {
    // Regression test: a bullet marker's text must stay on the same line as the
    // marker, which a block-level <p> child breaks onto its own line.
    const { container } = render(
      <li>
        <Prose inline>{'White blundered on move 4.'}</Prose>
      </li>,
    );
    expect(container.querySelector('p')).not.toBeInTheDocument();
    expect(screen.getByText(/White blundered on move 4\.?/)).toBeInTheDocument();
  });

  it('inline mode still highlights chess notation and keywords', () => {
    render(
      <ul>
        <li>
          <Prose inline>{'Nf3 was a mistake.'}</Prose>
        </li>
      </ul>,
    );
    expect(screen.getByText('Nf3')).toBeInTheDocument();
    expect(screen.getByText('mistake')).toBeInTheDocument();
  });
});
