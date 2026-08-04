/**
 * `PatternFeedbackView` tests (Phase 19).
 *
 * Focused on the claim the UI must not overstate: an absent weakness reads as an absence
 * unless the backend says the streak is sustained. Everything else here is layout.
 */
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import type { PatternFeedback } from '../api/patternFeedback';

import { PatternFeedbackView } from './PatternFeedbackView';

function feedback(overrides: Partial<PatternFeedback> = {}): PatternFeedback {
  return {
    game_id: 'game-1',
    baseline_games: 20,
    sufficient_baseline: true,
    attributable: true,
    outcome: 'win',
    overall_band: 'above',
    repeated: [],
    improved: [],
    metrics: [],
    report: null,
    ...overrides,
  };
}

const HANGING_PIECE = {
  kind: 'motif' as const,
  name: 'hanging_piece',
  baseline_games_with_finding: 6,
  baseline_games: 20,
  occurrence_rate: 0.3,
};

describe('PatternFeedbackView', () => {
  it('shows a repeat with its move numbers and how often it recurs', () => {
    render(
      <PatternFeedbackView
        feedback={feedback({ repeated: [{ ...HANGING_PIECE, move_numbers: [24] }] })}
      />,
    );

    expect(screen.getByText('Hanging piece')).toBeInTheDocument();
    expect(screen.getByText(/move 24/)).toBeInTheDocument();
    expect(screen.getByText(/6 of your last 20 games/)).toBeInTheDocument();
  });

  it('describes a single clean game as an absence, not a fix', () => {
    render(
      <PatternFeedbackView
        feedback={feedback({
          improved: [{ ...HANGING_PIECE, clear_streak: 1, sustained: false }],
        })}
      />,
    );

    expect(screen.getByText(/not in this game/)).toBeInTheDocument();
    expect(screen.queryByText(/games running/)).not.toBeInTheDocument();
  });

  it('describes a sustained streak by its run of games', () => {
    render(
      <PatternFeedbackView
        feedback={feedback({
          improved: [{ ...HANGING_PIECE, clear_streak: 4, sustained: true }],
        })}
      />,
    );

    expect(screen.getByText(/clear for 4 games running/)).toBeInTheDocument();
  });

  it('always states the sample the verdict rests on', () => {
    render(<PatternFeedbackView feedback={feedback({ overall_band: 'well_above' })} />);

    expect(screen.getByText('Well above your usual')).toBeInTheDocument();
    expect(screen.getByText(/previous 20 analyzed games/)).toBeInTheDocument();
  });

  it('formats each metric in its own units against the baseline mean', () => {
    render(
      <PatternFeedbackView
        feedback={feedback({
          metrics: [
            {
              name: 'accuracy',
              value: 78.4,
              baseline_mean: 71.2,
              z_score: 1.3,
              band: 'well_above',
            },
            {
              name: 'blunder_rate',
              value: 0.02,
              baseline_mean: 0.061,
              z_score: 0.9,
              band: 'above',
            },
          ],
        })}
      />,
    );

    expect(screen.getByText('78.4%')).toBeInTheDocument();
    expect(screen.getByText('vs 71.2%')).toBeInTheDocument();
    // A rate renders as a percentage rather than a raw 0.02.
    expect(screen.getByText('2.0%')).toBeInTheDocument();
  });

  it('offers no regenerate control when the caller supplies no handler', () => {
    render(<PatternFeedbackView feedback={feedback()} />);

    expect(screen.queryByRole('button', { name: /regenerate/i })).not.toBeInTheDocument();
  });

  it('regenerates on request, and reports that it is working', async () => {
    const onRegenerate = vi.fn();
    const { rerender } = render(
      <PatternFeedbackView feedback={feedback()} onRegenerate={onRegenerate} />,
    );

    // Queried by accessible name, not by text: the control is icon-only, so `aria-label`
    // is the only name it has.
    await userEvent.click(screen.getByRole('button', { name: 'Regenerate feedback' }));
    expect(onRegenerate).toHaveBeenCalledOnce();

    // While in flight the button must not be clickable again — each press spends an
    // LLM call.
    rerender(
      <PatternFeedbackView feedback={feedback()} onRegenerate={onRegenerate} isRegenerating />,
    );
    expect(screen.getByRole('button', { name: 'Regenerating feedback…' })).toBeDisabled();
  });

  it('says so plainly when nothing recurred', () => {
    render(<PatternFeedbackView feedback={feedback()} />);

    expect(
      screen.getByText('None of your recurring habits showed up this game.'),
    ).toBeInTheDocument();
  });
});
