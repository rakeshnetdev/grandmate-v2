/**
 * ThemeToggle + ThemeProvider tests: toggling flips `data-theme` on `<html>` and
 * persists to `localStorage`, and a stored preference is picked up on mount.
 * `localStorage` and `data-theme` reset per test via the global setup/`afterEach`.
 */
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it } from 'vitest';

import { renderWithProviders } from '@/test/render';

import { ThemeToggle } from './ThemeToggle';

const STORAGE_KEY = 'grandmate-theme';

afterEach(() => {
  document.documentElement.removeAttribute('data-theme');
});

describe('ThemeToggle', () => {
  it('has no data-theme attribute until the user picks one', () => {
    renderWithProviders(<ThemeToggle />);
    expect(document.documentElement.getAttribute('data-theme')).toBeNull();
  });

  it('sets data-theme and persists it on click', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ThemeToggle />);

    await user.click(screen.getByRole('button'));

    const applied = document.documentElement.getAttribute('data-theme');
    expect(applied).toMatch(/^(light|dark)$/);
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe(applied);
  });

  it('flips back on a second click', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ThemeToggle />);

    await user.click(screen.getByRole('button'));
    const first = document.documentElement.getAttribute('data-theme');
    await user.click(screen.getByRole('button'));
    const second = document.documentElement.getAttribute('data-theme');

    expect(second).not.toBe(first);
  });

  it('picks up a previously stored preference on mount', () => {
    window.localStorage.setItem(STORAGE_KEY, 'dark');

    renderWithProviders(<ThemeToggle />);

    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    expect(screen.getByRole('button', { name: 'Switch to light theme' })).toBeInTheDocument();
  });
});
