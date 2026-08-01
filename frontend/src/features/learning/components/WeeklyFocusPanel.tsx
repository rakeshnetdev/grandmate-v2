/**
 * "This week's focus" — a short, actionable to-do built from the profile's existing
 * analytics and training plan.
 *
 * Nothing here is newly analysed. The training summary is the one the backend already
 * generated (`domain/reports/training_service.py`), and the tiles are a deterministic
 * ranking of aggregates that were already computed — see `lib/selection.ts`. This panel
 * decides *presentation order*, never chess truth.
 *
 * "Give me next" walks further down the same ranking rather than re-querying: the ranked
 * list is already in memory, so advancing a round is a slice, not a fetch. Everything
 * passed over collects in the completed panel at the bottom, still linked, so a reader
 * can go back to something they worked through earlier.
 *
 * Each tile links out to Lichess so the next step after reading is one click, rather than
 * the reader having to translate "you keep missing forks" into a search.
 */
import { useState } from 'react';

import { BookOpen, ExternalLink, RotateCcw, Swords } from 'lucide-react';

import { useProfileAnalytics } from '@/features/analytics';
import { WINDOW_OPTIONS } from '@/features/analytics/lib/constants';
import type { PersonaValue } from '@/features/reports';
import { useTrainingPlan } from '@/features/training';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';

import { humaniseMotif, lichessOpeningUrl, lichessPuzzleUrl } from '../lib/lichess';
import {
  FOCUS_COUNT,
  paginateFocus,
  rankMotifsToLearn,
  rankOpeningsToLearn,
} from '../lib/selection';

interface WeeklyFocusPanelProps {
  profileId?: string;
  /** Which persona's training summary to show. Framing only — the facts are identical. */
  persona?: PersonaValue;
}

/**
 * Tile palette. Built on the same formula as `shared/lib/classification.ts`'s badges —
 * low-opacity fills over the theme's own surface, lighter text in dark mode — so these
 * read as part of the same system rather than a second colour language.
 *
 * Two hues only, and both muted: the colour carries *kind* (study vs drill), not
 * severity. A saturated palette would imply these items are alarming, when they are just
 * this week's list.
 */
const TILE_TONE = {
  opening: {
    tile: 'bg-indigo-500/5 border-indigo-500/20 hover:bg-indigo-500/10 hover:border-indigo-500/30',
    chip: 'bg-indigo-500/15 text-indigo-700 dark:text-indigo-400',
    title: 'text-indigo-900 dark:text-indigo-200',
  },
  tactic: {
    tile: 'bg-amber-500/5 border-amber-500/20 hover:bg-amber-500/10 hover:border-amber-500/30',
    chip: 'bg-amber-500/15 text-amber-700 dark:text-amber-400',
    title: 'text-amber-900 dark:text-amber-200',
  },
} as const;

type TileTone = keyof typeof TILE_TONE;

/** One to-do tile: a coloured marker, a label, a reason, and an outbound link. */
function FocusTile({
  icon: Icon,
  title,
  reason,
  href,
  tone,
}: {
  icon: typeof BookOpen;
  title: string;
  reason: string;
  href: string | null;
  tone: TileTone;
}) {
  const styles = TILE_TONE[tone];

  const body = (
    <>
      <span
        className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md ${styles.chip}`}
      >
        <Icon className="h-4 w-4" aria-hidden="true" />
      </span>
      <span className="min-w-0 flex-1">
        <span className={`flex items-center gap-1.5 text-sm font-medium ${styles.title}`}>
          {title}
          {href && <ExternalLink className="h-3 w-3 shrink-0 opacity-60" aria-hidden="true" />}
        </span>
        <span className="mt-0.5 block text-xs text-muted-foreground">{reason}</span>
      </span>
    </>
  );

  const base = `flex items-start gap-3 rounded-lg border p-3 transition-colors ${styles.tile}`;

  // No mapping means no link rather than a guessed URL that would 404 on Lichess.
  if (!href) {
    return <li className={base}>{body}</li>;
  }

  return (
    <li>
      <a href={href} target="_blank" rel="noreferrer" className={base}>
        {body}
      </a>
    </li>
  );
}

/**
 * Already-worked-through items. Deliberately a plain list rather than tiles: these are a
 * reference you scan, not the thing you are meant to act on now, and giving them tile
 * weight would compete with the current round for attention.
 */
function CompletedList({
  openings,
  motifs,
}: {
  openings: { family: string }[];
  motifs: { name: string }[];
}) {
  if (openings.length === 0 && motifs.length === 0) return null;

  const items = [
    ...openings.map((o) => ({
      key: `o-${o.family}`,
      label: o.family,
      href: lichessOpeningUrl(o.family),
    })),
    ...motifs.map((m) => ({
      key: `m-${m.name}`,
      label: humaniseMotif(m.name),
      href: lichessPuzzleUrl(m.name),
    })),
  ];

  return (
    <section className="border-t border-border pt-4">
      <h3 className="text-sm font-semibold">Already covered</h3>
      <p className="mt-1 text-xs text-muted-foreground">
        Items from earlier rounds. Still linked if you want another pass.
      </p>
      <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
        {items.map((item) => (
          <li key={item.key} className="text-xs">
            {item.href ? (
              <a
                href={item.href}
                target="_blank"
                rel="noreferrer"
                className="text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
              >
                {item.label}
              </a>
            ) : (
              <span className="text-muted-foreground">{item.label}</span>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

export function WeeklyFocusPanel({ profileId, persona = 'self_learner' }: WeeklyFocusPanelProps) {
  // The widest window gives the steadiest signal for a weekly plan; the Overview tab is
  // where a reader goes to slice by shorter windows.
  const windowSize = WINDOW_OPTIONS.at(-1) ?? WINDOW_OPTIONS[0];
  const { data: analytics, isLoading } = useProfileAnalytics(windowSize, profileId);
  const { data: plan } = useTrainingPlan(windowSize, persona, profileId);

  // Round state is intentionally in-memory: it is a reading position, not a record of
  // work done, and persisting it would imply a completion the system cannot verify.
  const [round, setRound] = useState(0);

  const rankedOpenings = rankOpeningsToLearn(analytics);
  const rankedMotifs = rankMotifsToLearn(analytics);
  const openings = paginateFocus(rankedOpenings, round);
  const motifs = paginateFocus(rankedMotifs, round);

  const hasNextRound =
    rankedOpenings.length > (round + 1) * FOCUS_COUNT ||
    rankedMotifs.length > (round + 1) * FOCUS_COUNT;

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Computing…</p>;
  }

  if (!analytics || analytics.games_included === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No analyzed games yet. Import and analyze some games to get a weekly focus.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      <section className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold">
            This week&apos;s focus{round > 0 && ` · round ${round + 1}`}
          </h2>
          <p className="mt-1 text-xs text-muted-foreground">
            Drawn from your last {analytics.games_included} analyzed games. Each item opens the
            matching Lichess trainer.
          </p>
          {!analytics.sufficient_sample && (
            <p className="mt-2 text-xs text-muted-foreground">
              Small sample — treat these as suggestions rather than conclusions.
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {round > 0 && (
            <Button variant="ghost" size="sm" onClick={() => setRound(0)}>
              <RotateCcw className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
              Start over
            </Button>
          )}
          <Button size="sm" onClick={() => setRound((r) => r + 1)} disabled={!hasNextRound}>
            Give me next
          </Button>
        </div>
      </section>

      {!hasNextRound && round > 0 && (
        <p className="text-xs text-muted-foreground">
          That is everything your games support right now. Analyze more games for a longer list.
        </p>
      )}

      {plan?.summary && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Where you stand</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">{plan.summary}</p>
          </CardContent>
        </Card>
      )}

      <section>
        <h3 className="mb-2 text-sm font-semibold">Openings to study</h3>
        {openings.current.length === 0 ? (
          <p className="text-xs text-muted-foreground">Nothing further in this round.</p>
        ) : (
          <ul className="grid gap-2 md:grid-cols-3">
            {openings.current.map((o) => (
              <FocusTile
                key={o.family}
                icon={BookOpen}
                title={o.family}
                reason={
                  o.win_rate === null
                    ? `${o.games} games`
                    : `${Math.round(o.win_rate * 100)}% win rate over ${o.games} games`
                }
                href={lichessOpeningUrl(o.family)}
                tone="opening"
              />
            ))}
          </ul>
        )}
      </section>

      <section>
        <h3 className="mb-2 text-sm font-semibold">Tactics to drill</h3>
        {motifs.current.length === 0 ? (
          <p className="text-xs text-muted-foreground">Nothing further in this round.</p>
        ) : (
          <ul className="grid gap-2 md:grid-cols-3">
            {motifs.current.map((m) => (
              <FocusTile
                key={m.name}
                icon={Swords}
                title={humaniseMotif(m.name)}
                reason={`Appeared in ${m.games_with_finding} of your last ${analytics.games_included} games`}
                href={lichessPuzzleUrl(m.name)}
                tone="tactic"
              />
            ))}
          </ul>
        )}
      </section>

      <CompletedList openings={openings.completed} motifs={motifs.completed} />
    </div>
  );
}
