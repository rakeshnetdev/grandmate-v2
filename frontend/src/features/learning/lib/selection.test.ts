/**
 * Weekly-focus selection tests: the ranking is what decides which six things a learner
 * is told to work on, so the ordering rules and the sample-size floor are worth pinning.
 */
import { describe, expect, it } from 'vitest';

import type { ProfileAnalytics } from '@/features/analytics';

import { lichessOpeningUrl, lichessPuzzleUrl } from './lichess';
import { rankMotifsToLearn, rankOpeningsToLearn, splitFocus } from './selection';

function analytics(overrides: Partial<ProfileAnalytics>): ProfileAnalytics {
  return {
    profile_id: 'p1',
    window_size: 60,
    games_included: 30,
    sufficient_sample: true,
    snapshot_version: 'v1',
    computed_at: '2026-07-31T00:00:00Z',
    accuracy: { current: 80, previous: null, delta: null },
    classification_rates: { current: {}, previous: {}, delta: null },
    critical_moment_rate: { current: 0.1, previous: null, delta: null },
    opening_family_performance: [],
    color_segmentation: [],
    time_control_segmentation: [],
    recurring_weaknesses: [],
    ...overrides,
  };
}

function opening(family: string, games: number, win_rate: number | null) {
  return { family, games, wins: 0, draws: 0, losses: 0, win_rate, average_accuracy: 70 };
}

describe('rankOpeningsToLearn', () => {
  it('ranks the weakest families first', () => {
    const result = rankOpeningsToLearn(
      analytics({
        opening_family_performance: [
          opening('Sicilian Defense', 10, 0.7),
          opening('French Defense', 10, 0.2),
          opening('Caro-Kann Defense', 10, 0.45),
          opening('London System', 10, 0.3),
        ],
      }),
    );

    expect(result.slice(0, 3).map((o) => o.family)).toEqual([
      'French Defense',
      'London System',
      'Caro-Kann Defense',
    ]);
  });

  it('ignores families with too few games to mean anything', () => {
    const result = rankOpeningsToLearn(
      analytics({
        opening_family_performance: [opening('Budapest Gambit', 1, 0.0), opening('Slav', 4, 0.6)],
      }),
    );

    expect(result.map((o) => o.family)).toEqual(['Slav']);
  });

  it('sorts an uncomputable win rate last rather than treating it as zero', () => {
    const result = rankOpeningsToLearn(
      analytics({
        opening_family_performance: [opening('Unknown', 5, null), opening('Pirc', 5, 0.1)],
      }),
    );

    expect(result[0]?.family).toBe('Pirc');
  });
});

describe('rankMotifsToLearn', () => {
  it('ranks the most frequent motifs first and excludes strategic themes', () => {
    const result = rankMotifsToLearn(
      analytics({
        recurring_weaknesses: [
          { kind: 'theme', name: 'bad_bishop', games_with_finding: 20, occurrence_rate: 0.9 },
          { kind: 'motif', name: 'fork', games_with_finding: 12, occurrence_rate: 0.4 },
          { kind: 'motif', name: 'pin', games_with_finding: 18, occurrence_rate: 0.6 },
          { kind: 'motif', name: 'skewer', games_with_finding: 6, occurrence_rate: 0.2 },
          { kind: 'motif', name: 'x_ray', games_with_finding: 3, occurrence_rate: 0.1 },
        ],
      }),
    );

    expect(result.slice(0, 3).map((m) => m.name)).toEqual(['pin', 'fork', 'skewer']);
  });
});

describe('lichess links', () => {
  it('maps every motif we detect to a puzzle theme', () => {
    // The full taxonomy from db/models/patterns.py::TacticalMotifType. A detector whose
    // motif has no mapping would silently render as unclickable text.
    const allMotifs = [
      'fork',
      'pin',
      'skewer',
      'discovered_attack',
      'double_check',
      'back_rank_mate',
      'smothered_mate',
      'hanging_piece',
      'removing_the_defender',
      'x_ray',
    ];

    for (const motif of allMotifs) {
      expect(lichessPuzzleUrl(motif)).toMatch(/^https:\/\/lichess\.org\/training\/\w+$/);
    }
  });

  it('returns null for an unmapped motif rather than guessing a 404 URL', () => {
    expect(lichessPuzzleUrl('zwischenzug')).toBeNull();
  });

  it('builds opening URLs with underscores', () => {
    expect(lichessOpeningUrl('Sicilian Defense')).toBe(
      'https://lichess.org/opening/Sicilian_Defense',
    );
  });
});

describe('splitFocus', () => {
  const ranked = ['a', 'b', 'c', 'd', 'e', 'f', 'g'];
  const id = (s: string) => s;

  it('shows the first three and nothing covered when nothing has been covered', () => {
    expect(splitFocus(ranked, id, new Set())).toEqual({
      current: ['a', 'b', 'c'],
      completed: [],
    });
  });

  it('skips covered items and shows the next three', () => {
    expect(splitFocus(ranked, id, new Set(['a', 'b', 'c']))).toEqual({
      current: ['d', 'e', 'f'],
      completed: ['a', 'b', 'c'],
    });
  });

  it('stays correct when the ranking reorders around a covered item', () => {
    // 'a' moved to the end after new games were analyzed; it is still covered, and the
    // three current items are the next uncovered ones in the new order.
    const reordered = ['d', 'b', 'e', 'c', 'f', 'g', 'a'];

    const result = splitFocus(reordered, id, new Set(['a', 'b']));

    expect(result.current).toEqual(['d', 'e', 'c']);
    expect(result.completed).toEqual(['b', 'a']);
  });

  it('returns a short list rather than padding it', () => {
    expect(splitFocus(ranked, id, new Set(['a', 'b', 'c', 'd', 'e'])).current).toEqual(['f', 'g']);
  });

  it('runs out cleanly once everything is covered', () => {
    expect(splitFocus(ranked, id, new Set(ranked)).current).toEqual([]);
  });
});
