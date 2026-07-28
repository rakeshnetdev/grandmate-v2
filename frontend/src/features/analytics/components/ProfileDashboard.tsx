/**
 * Profile analytics dashboard (Phase 8): multi-game aggregation over a profile's most
 * recent games, recomputed on every load — see `domain/analytics/service.py`'s docstring
 * on why that's cheap enough to do rather than caching.
 *
 * Deterministic only, same boundary as the single-game analysis view (Phase 8a): no LLM
 * narrative, no RAG. Every number here is a direct aggregate of already-computed
 * per-game data. Each section below is its own file — see the `components/` folder —
 * this component only composes them.
 */
import { useState } from 'react';

import { useProfileAnalytics } from '../hooks/useAnalytics';
import { WINDOW_OPTIONS } from '../lib/constants';
import { ClassificationRateTable } from './ClassificationRateTable';
import { ColorSegmentationTable } from './ColorSegmentationTable';
import { OpeningFamilyTable } from './OpeningFamilyTable';
import { RecurringWeaknessList } from './RecurringWeaknessList';
import { SampleSizeBanner } from './SampleSizeBanner';
import { StatTile } from './StatTile';
import { TimeControlTable } from './TimeControlTable';
import { WindowSelector } from './WindowSelector';

interface ProfileDashboardProps {
  /** `undefined` means the caller's own SELF profile (Phase 8b). */
  profileId?: string;
}

export function ProfileDashboard({ profileId }: ProfileDashboardProps) {
  const [windowSize, setWindowSize] = useState<number>(WINDOW_OPTIONS[0]);
  const { data: analytics, isLoading } = useProfileAnalytics(windowSize, profileId);

  return (
    <div className="space-y-6">
      <WindowSelector value={windowSize} onChange={setWindowSize} />

      {isLoading || !analytics ? (
        <p className="text-sm text-muted-foreground">Computing…</p>
      ) : analytics.games_included === 0 ? (
        <p className="text-sm text-muted-foreground">
          No analyzed games yet. Import and analyze some games to see trends here.
        </p>
      ) : (
        <>
          {!analytics.sufficient_sample && (
            <SampleSizeBanner gamesIncluded={analytics.games_included} />
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            <StatTile
              label="Accuracy"
              value={analytics.accuracy.current === null ? '—' : `${analytics.accuracy.current}%`}
              delta={analytics.accuracy.delta}
              formatDelta={(d) => `${d > 0 ? '+' : ''}${d.toFixed(1)} pts`}
              higherIsBetter
            />
            <StatTile
              label="Critical moments per game"
              value={
                analytics.critical_moment_rate.current === null
                  ? '—'
                  : analytics.critical_moment_rate.current.toString()
              }
              delta={analytics.critical_moment_rate.delta}
              formatDelta={(d) => `${d > 0 ? '+' : ''}${d.toFixed(2)}`}
              higherIsBetter={false}
            />
          </div>

          <section>
            <h2 className="mb-2 text-sm font-semibold">Move quality</h2>
            <ClassificationRateTable analytics={analytics} />
          </section>

          <section>
            <h2 className="mb-2 text-sm font-semibold">Recurring weaknesses</h2>
            <RecurringWeaknessList weaknesses={analytics.recurring_weaknesses} />
          </section>

          <section>
            <h2 className="mb-2 text-sm font-semibold">Opening family performance</h2>
            <OpeningFamilyTable families={analytics.opening_family_performance} />
          </section>

          <div className="grid gap-6 sm:grid-cols-2">
            <section>
              <h2 className="mb-2 text-sm font-semibold">By color</h2>
              <ColorSegmentationTable segments={analytics.color_segmentation} />
            </section>
            <section>
              <h2 className="mb-2 text-sm font-semibold">By time control</h2>
              <TimeControlTable segments={analytics.time_control_segmentation} />
            </section>
          </div>
        </>
      )}
    </div>
  );
}
