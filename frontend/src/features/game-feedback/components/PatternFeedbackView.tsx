/**
 * This game against the player's recent history (Phase 19, D-037).
 *
 * Three sections in the order a player actually asks the questions: what happened again,
 * what did not, and how good was this game overall. The deterministic numbers lead and
 * the generated prose follows underneath — a claim about someone's own habits should show
 * its sample size, not just assert itself.
 *
 * The one wording rule that matters: a weakness absent from a single game is written as
 * an absence ("Not in this game"), and only a sustained streak is written as a habit
 * broken. The backend decides which of the two applies (`sustained`); this component only
 * has to avoid flattening the distinction.
 */
import { Button } from '@/shared/components/ui/button';
import { PieceList, PieceListItem } from '@/shared/components/ui/piece-list';
import { Prose } from '@/shared/lib/prose';

import type {
  ImprovedWeakness,
  MetricComparison,
  PatternFeedback,
  RepeatedWeakness,
} from '../api/patternFeedback';
import {
  BAND_LABELS,
  BAND_TONES,
  metricLabel,
  metricValue,
  moveNumbersText,
  occurrenceText,
  weaknessLabel,
} from '../lib/format';

function SectionHeading({ children }: { children: React.ReactNode }) {
  return <h3 className="text-sm font-semibold">{children}</h3>;
}

function RepeatedList({ items }: { items: RepeatedWeakness[] }) {
  return (
    <PieceList>
      {items.map((item) => (
        <PieceListItem
          key={`${item.kind}-${item.name}`}
          piece="rook"
          tone="text-amber-600/70 dark:text-amber-400/70"
        >
          <span className="font-medium">{weaknessLabel(item.name)}</span>
          {item.move_numbers.length > 0 && (
            <span className="text-muted-foreground"> — {moveNumbersText(item.move_numbers)}</span>
          )}
          <span className="text-muted-foreground">
            {' '}
            · {occurrenceText(item.baseline_games_with_finding, item.baseline_games)}
          </span>
        </PieceListItem>
      ))}
    </PieceList>
  );
}

function ImprovedList({ items }: { items: ImprovedWeakness[] }) {
  return (
    <PieceList>
      {items.map((item) => (
        <PieceListItem
          key={`${item.kind}-${item.name}`}
          piece="pawn"
          tone="text-emerald-600/70 dark:text-emerald-400/70"
        >
          <span className="font-medium">{weaknessLabel(item.name)}</span>
          <span className="text-muted-foreground">
            {' '}
            — {item.sustained ? `clear for ${item.clear_streak} games running` : 'not in this game'}
          </span>
          <span className="text-muted-foreground">
            {' '}
            · was {occurrenceText(item.baseline_games_with_finding, item.baseline_games)}
          </span>
        </PieceListItem>
      ))}
    </PieceList>
  );
}

function MetricRow({ metric }: { metric: MetricComparison }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1.5">
      <span className="text-sm text-muted-foreground">{metricLabel(metric.name)}</span>
      <span className="flex items-baseline gap-2 text-sm">
        <span className="font-medium tabular-nums">{metricValue(metric.name, metric.value)}</span>
        <span className="text-xs text-muted-foreground tabular-nums">
          vs {metricValue(metric.name, metric.baseline_mean)}
        </span>
        <span className={`text-xs ${BAND_TONES[metric.band]}`}>{BAND_LABELS[metric.band]}</span>
      </span>
    </div>
  );
}

interface PatternFeedbackViewProps {
  feedback: PatternFeedback;
  /** Discards the stored write-up and generates a new one. Spends an LLM call, so it is
   * only ever driven by this button — never by a refetch. */
  onRegenerate?: () => void;
  isRegenerating?: boolean;
}

export function PatternFeedbackView({
  feedback,
  onRegenerate,
  isRegenerating = false,
}: PatternFeedbackViewProps) {
  const { repeated, improved, metrics, report } = feedback;

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className={`text-sm font-medium ${BAND_TONES[feedback.overall_band]}`}>
            {BAND_LABELS[feedback.overall_band]}
          </p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Compared against your previous {feedback.baseline_games} analyzed games.
          </p>
        </div>
        {onRegenerate && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={isRegenerating}
            onClick={onRegenerate}
          >
            {isRegenerating ? 'Regenerating…' : 'Regenerate'}
          </Button>
        )}
      </div>

      {report && <Prose>{report.summary}</Prose>}

      <section className="space-y-2">
        <SectionHeading>Repeated in this game</SectionHeading>
        {repeated.length > 0 ? (
          <RepeatedList items={repeated} />
        ) : (
          <p className="text-sm text-muted-foreground">
            None of your recurring habits showed up this game.
          </p>
        )}
      </section>

      {improved.length > 0 && (
        <section className="space-y-2">
          <SectionHeading>Stayed away</SectionHeading>
          <ImprovedList items={improved} />
        </section>
      )}

      {metrics.length > 0 && (
        <section className="space-y-1">
          <SectionHeading>How this game measured up</SectionHeading>
          <div className="divide-y divide-border">
            {metrics.map((metric) => (
              <MetricRow key={metric.name} metric={metric} />
            ))}
          </div>
        </section>
      )}

      {report && report.findings.length > 0 && (
        <section className="space-y-2">
          <SectionHeading>What this means</SectionHeading>
          <PieceList>
            {report.findings.map((finding, index) => (
              <PieceListItem
                key={`${finding.fact_ids.join('-')}-${index}`}
                piece="knight"
                tone="text-indigo-600/70 dark:text-indigo-400/70"
              >
                <Prose>{finding.text}</Prose>
              </PieceListItem>
            ))}
          </PieceList>
        </section>
      )}

      {report && report.recommendations.length > 0 && (
        <section className="space-y-2">
          <SectionHeading>Next Steps</SectionHeading>
          <PieceList>
            {report.recommendations.map((recommendation) => (
              <PieceListItem key={recommendation} piece="queen" tone="text-foreground/50">
                <Prose inline>{recommendation}</Prose>
              </PieceListItem>
            ))}
          </PieceList>
        </section>
      )}
    </div>
  );
}
