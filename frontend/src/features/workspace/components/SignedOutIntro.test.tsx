/**
 * `SignedOutIntro` tests: the three explanatory cards and the login prompt above them.
 *
 * Asserts on headings rather than body copy — the wording is expected to be edited, the
 * three-card structure is not, and a test that breaks on every copy tweak trains people
 * to update it without reading it.
 */
import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { renderWithProviders } from '@/test/render';

import { SignedOutIntro } from './SignedOutIntro';

describe('SignedOutIntro', () => {
  it('shows the product name and how to get in', () => {
    renderWithProviders(<SignedOutIntro />);

    expect(screen.getByRole('heading', { name: 'GrandMate' })).toBeInTheDocument();
    expect(screen.getByText(/Log in with Lichess or Chess\.com/)).toBeInTheDocument();
  });

  it('explains what it is, how it helps, and who it is for', () => {
    renderWithProviders(<SignedOutIntro />);

    expect(screen.getByText('What it is')).toBeInTheDocument();
    expect(screen.getByText('How it helps')).toBeInTheDocument();
    expect(screen.getByText('Who it is for')).toBeInTheDocument();
  });

  it('renders each card with its own heading', () => {
    renderWithProviders(<SignedOutIntro />);

    expect(screen.getByRole('heading', { name: 'Analysis you can trust' })).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: 'Patterns, not just blunders' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Built for how you learn' })).toBeInTheDocument();
  });
});
