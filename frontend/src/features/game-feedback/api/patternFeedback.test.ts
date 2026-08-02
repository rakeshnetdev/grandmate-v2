/**
 * Contract test for the pattern-feedback schema (Phase 19).
 *
 * Exists because of a real bug: the embedded report reuses the shared `gameReportSchema`,
 * whose finding-`kind` enum did not list this format's vocabulary. Zod rejected the whole
 * response, and the tab showed "could not load" against a backend that was answering 200.
 * Component tests could not catch it — they build objects directly instead of parsing —
 * so the payload itself needs a test.
 *
 * The fixture below is a trimmed copy of a real response from
 * `GET /api/v1/reports/games/{id}/pattern-feedback`.
 */
import { describe, expect, it } from 'vitest';

import { patternFeedbackSchema } from './patternFeedback';

const REAL_RESPONSE = {
  game_id: '55284369-143c-4df1-a1af-b68cb643628e',
  baseline_games: 20,
  sufficient_baseline: true,
  attributable: true,
  outcome: 'draw',
  overall_band: 'well_below',
  repeated: [
    {
      kind: 'theme',
      name: 'development_lag',
      baseline_games_with_finding: 17,
      baseline_games: 20,
      occurrence_rate: 0.85,
      move_numbers: [11],
    },
  ],
  improved: [
    {
      kind: 'motif',
      name: 'pin',
      baseline_games_with_finding: 8,
      baseline_games: 20,
      occurrence_rate: 0.4,
      clear_streak: 1,
      sustained: false,
    },
  ],
  metrics: [
    { name: 'accuracy', value: 44.4, baseline_mean: 55.59, z_score: -0.62, band: 'below' },
    {
      name: 'critical_moments',
      value: 10.0,
      baseline_mean: 5.95,
      z_score: null,
      band: 'in_line',
    },
  ],
  report: {
    id: '490724f8-b3a1-427c-94ba-acb4b0d01633',
    game_id: '55284369-143c-4df1-a1af-b68cb643628e',
    persona: 'self_learner',
    source: 'llm',
    model: 'gpt-4o-mini-2024-07-18',
    analysis_version: 'sf-d12-dd18-t50.100.300',
    summary: 'This game resulted in a draw.',
    findings: [
      { fact_ids: ['repeat-theme-development_lag'], text: 'You lagged again.', kind: 'repeated' },
      { fact_ids: ['improved-motif-pin'], text: 'No pins this game.', kind: 'improved' },
      { fact_ids: ['verdict-accuracy'], text: 'Below your average.', kind: 'verdict' },
    ],
    recommendations: ['Develop your pieces sooner.'],
    grounded: true,
    created_at: '2026-08-02T06:30:54.332608Z',
  },
};

describe('patternFeedbackSchema', () => {
  it('accepts a real backend response, including every finding kind this format uses', () => {
    const parsed = patternFeedbackSchema.parse(REAL_RESPONSE);

    expect(parsed.report?.findings.map((f) => f.kind)).toEqual([
      'repeated',
      'improved',
      'verdict',
    ]);
  });

  it('accepts the thin-baseline response, where there is no report at all', () => {
    const parsed = patternFeedbackSchema.parse({
      ...REAL_RESPONSE,
      baseline_games: 2,
      sufficient_baseline: false,
      repeated: [],
      improved: [],
      metrics: [],
      report: null,
    });

    expect(parsed.report).toBeNull();
    expect(parsed.sufficient_baseline).toBe(false);
  });
});
