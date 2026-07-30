/**
 * Opening match, tactical motifs, and strategic themes for the selected game (Phase
 * 16a, D-035) — the workspace's "Patterns" tab, split out of `GameAnalysisView`'s
 * former single-scroll `PatternsSummary` section.
 */
import { useGameAnalysis, useGamePatterns } from '@/features/games';
import type { GamePatterns } from '@/features/games';

function PatternsSummary({ patterns }: { patterns: GamePatterns }) {
  if (!patterns.opening && patterns.motifs.length === 0 && patterns.themes.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">No opening match or findings for this game.</p>
    );
  }

  return (
    <div className="space-y-4 text-sm">
      {patterns.opening && (
        <div>
          <h3 className="mb-1 text-sm font-semibold">Opening</h3>
          <p>
            <span className="font-medium">{patterns.opening.opening_name}</span>{' '}
            <span className="text-muted-foreground">({patterns.opening.eco})</span>
          </p>
        </div>
      )}
      {patterns.motifs.length > 0 && (
        <div>
          <h3 className="mb-1 text-sm font-semibold">Tactical motifs</h3>
          <ul className="space-y-1 text-muted-foreground">
            {patterns.motifs.map((m, index) => (
              <li key={`${m.motif}-${m.ply}-${index}`}>
                {m.motif.replace(/_/g, ' ')} (ply {m.ply}, {m.side})
              </li>
            ))}
          </ul>
        </div>
      )}
      {patterns.themes.length > 0 && (
        <div>
          <h3 className="mb-1 text-sm font-semibold">Strategic themes</h3>
          <ul className="space-y-1 text-muted-foreground">
            {patterns.themes.map((t, index) => (
              <li key={`${t.theme}-${t.ply}-${index}`}>
                {t.theme.replace(/_/g, ' ')} (ply {t.ply}, {t.side})
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

interface PatternsTabProps {
  gameId: string;
  profileId?: string;
}

export function PatternsTab({ gameId, profileId }: PatternsTabProps) {
  const { data: analysis, isError: analysisErrored } = useGameAnalysis(gameId, profileId);
  const {
    data: patterns,
    isLoading,
    isError: patternsErrored,
  } = useGamePatterns(gameId, profileId, {
    enabled: Boolean(analysis),
  });

  if (analysisErrored || patternsErrored) {
    return <p className="text-sm text-destructive">Could not load this game's patterns.</p>;
  }

  if (!analysis) {
    return (
      <p className="text-sm text-muted-foreground">
        Patterns are available once this game's analysis finishes.
      </p>
    );
  }

  if (isLoading || !patterns) {
    return <p className="text-sm text-muted-foreground">Loading patterns…</p>;
  }

  return <PatternsSummary patterns={patterns} />;
}
