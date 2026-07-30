/**
 * `StoryView` tests (Phase 16b): section grouping by `kind`, and the empty/no-sections
 * state. `ReportView`'s AI-generated/fallback badge is shared logic, not re-tested here.
 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { GameReport } from '../api/reports';

import { StoryView } from './StoryView';

function report(overrides: Partial<GameReport> = {}): GameReport {
  return {
    id: 'report-1',
    game_id: 'game-1',
    persona: 'self_learner',
    source: 'llm',
    model: 'gpt-4o-mini',
    analysis_version: 'test',
    summary: 'A close game decided in the middlegame.',
    findings: [],
    recommendations: [],
    grounded: true,
    created_at: '2026-07-29T00:00:00Z',
    ...overrides,
  };
}

describe('StoryView', () => {
  it('groups findings under their section headers by kind', () => {
    render(
      <StoryView
        report={report({
          findings: [
            { fact_ids: ['opening'], text: 'The Ruy Lopez was played.', kind: 'opening' },
            {
              fact_ids: ['move-20'],
              text: 'White won a pawn in the middlegame.',
              kind: 'middlegame',
            },
            { fact_ids: ['move-4'], text: 'Watch out for early queen sorties.', kind: 'lesson' },
          ],
        })}
      />,
    );

    expect(screen.getByText('Opening')).toBeInTheDocument();
    expect(screen.getByText('Middlegame')).toBeInTheDocument();
    expect(screen.getByText('Lessons')).toBeInTheDocument();
    expect(screen.queryByText('Endgame')).not.toBeInTheDocument();
  });

  it('shows a message when no story sections were generated', () => {
    render(<StoryView report={report({ findings: [] })} />);

    expect(screen.getByText(/No story sections were generated/)).toBeInTheDocument();
  });

  it('renders the deterministic-summary badge for a fallback story', () => {
    render(<StoryView report={report({ source: 'fallback' })} />);

    expect(screen.getByText('Deterministic summary')).toBeInTheDocument();
  });
});
