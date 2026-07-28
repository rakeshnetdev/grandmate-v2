/**
 * ProfileToggle tests: renders once the study profile is known, reflects the current
 * selection, and reports the study profile's own id (never a hardcoded one) on click.
 */
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { renderWithProviders } from '@/test/render';

import { ProfileToggle } from './ProfileToggle';

function mockFetchOnce(body: unknown) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(body),
    }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

const PROFILES = [
  { id: 'self-1', kind: 'self', display_name: 'magnus' },
  { id: 'study-1', kind: 'opponent', display_name: 'Study games' },
];

describe('ProfileToggle', () => {
  it('renders nothing before the study profile is known', () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => new Promise(() => {})),
    );

    renderWithProviders(<ProfileToggle value={undefined} onChange={vi.fn()} />);

    expect(screen.queryByRole('radiogroup')).not.toBeInTheDocument();
  });

  it("labels the study button with the profile's own display name", async () => {
    mockFetchOnce(PROFILES);

    renderWithProviders(<ProfileToggle value={undefined} onChange={vi.fn()} />);

    expect(await screen.findByRole('button', { name: 'Study games' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'My games' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });

  it('calls onChange with the study profile id when clicked', async () => {
    const user = userEvent.setup();
    mockFetchOnce(PROFILES);
    const onChange = vi.fn();

    renderWithProviders(<ProfileToggle value={undefined} onChange={onChange} />);
    await user.click(await screen.findByRole('button', { name: 'Study games' }));

    expect(onChange).toHaveBeenCalledWith('study-1');
  });

  it('calls onChange with undefined when "My games" is clicked', async () => {
    const user = userEvent.setup();
    mockFetchOnce(PROFILES);
    const onChange = vi.fn();

    renderWithProviders(<ProfileToggle value="study-1" onChange={onChange} />);
    await user.click(await screen.findByRole('button', { name: 'My games' }));

    expect(onChange).toHaveBeenCalledWith(undefined);
  });
});
