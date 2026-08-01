/**
 * `ContentPanel` tests: tab-gating logic (Phase 16a) — game-specific tabs only exist
 * once a game is selected, and an established "moves"/"analysis"/"patterns" tab value
 * falls back to Overview the moment no game is selected, rather than rendering a tab
 * with nothing to show. Underlying tab content (`OverviewTab`/`AnalysisTab`/etc.) fetches
 * real data and is exercised by live browser verification, not re-mocked here — this
 * file is only about which tabs exist and which one is active.
 */
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { renderWithProviders } from '@/test/render';

import { ContentPanel } from './ContentPanel';

afterEach(() => {
  vi.unstubAllGlobals();
});

function stubHangingFetch() {
  // Nested tab content (ProfileDashboard, PersonaReportPanel, etc.) fetches on mount —
  // parked deliberately so these tests assert on tab structure, not fetched content.
  vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})));
}

describe('ContentPanel', () => {
  it('offers only the profile-level tabs when no game is selected', () => {
    stubHangingFetch();
    renderWithProviders(<ContentPanel tab="overview" onTabChange={() => {}} />);

    expect(screen.getByRole('tab', { name: 'Overview' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Learning' })).toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: 'Analysis' })).not.toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: 'Moves' })).not.toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: 'Patterns' })).not.toBeInTheDocument();
  });

  it('offers every tab once a game is selected', () => {
    stubHangingFetch();
    renderWithProviders(
      <ContentPanel selectedGameId="game-1" tab="analysis" onTabChange={() => {}} />,
    );

    for (const label of ['Overview', 'Learning', 'Analysis', 'Moves', 'Patterns', 'Story']) {
      expect(screen.getByRole('tab', { name: label })).toBeInTheDocument();
    }
  });

  it('falls back to Overview when a game-specific tab value has no game selected', () => {
    stubHangingFetch();
    renderWithProviders(<ContentPanel tab="moves" onTabChange={() => {}} />);

    expect(screen.getByRole('tab', { name: 'Overview' })).toHaveAttribute('aria-selected', 'true');
  });

  it('keeps Learning selected with no game, since it is profile-level', () => {
    stubHangingFetch();
    renderWithProviders(<ContentPanel tab="learning" onTabChange={() => {}} />);

    expect(screen.getByRole('tab', { name: 'Learning' })).toHaveAttribute('aria-selected', 'true');
  });

  it('marks the given tab active once a game is selected', () => {
    stubHangingFetch();
    renderWithProviders(
      <ContentPanel selectedGameId="game-1" tab="moves" onTabChange={() => {}} />,
    );

    expect(screen.getByRole('tab', { name: 'Moves' })).toHaveAttribute('aria-selected', 'true');
  });

  it('calls onTabChange when a different tab is clicked', async () => {
    stubHangingFetch();
    const user = userEvent.setup();
    const onTabChange = vi.fn();
    renderWithProviders(
      <ContentPanel selectedGameId="game-1" tab="overview" onTabChange={onTabChange} />,
    );

    await user.click(screen.getByRole('tab', { name: 'Patterns' }));

    expect(onTabChange).toHaveBeenCalledWith('patterns');
  });
});
