/**
 * The workspace's "Pattern feedback" tab (Phase 19, D-037): this game measured against
 * the player's own recent history. Thin wrapper in the same shape as `StoryTab` — fetch,
 * loading, and error handling stay owned by the `game-feedback` feature's hook.
 */
import {
  InsufficientHistoryNotice,
  PatternFeedbackView,
  usePatternFeedback,
  useRegeneratePatternFeedback,
} from '@/features/game-feedback';
import { AnalyzingNotice, isAnalysisPending } from '@/features/reports';

interface PatternFeedbackTabProps {
  gameId: string;
  profileId?: string;
}

export function PatternFeedbackTab({ gameId, profileId }: PatternFeedbackTabProps) {
  const { data: feedback, isLoading, isError, error } = usePatternFeedback(gameId, profileId);
  const regenerate = useRegeneratePatternFeedback(gameId, profileId);

  // A game whose engine analysis has not finished is pending, not broken — same
  // distinction the report tabs make.
  if (isAnalysisPending(error)) {
    return <AnalyzingNotice gameId={gameId} />;
  }
  if (isError) {
    return (
      <p className="text-sm text-destructive">
        Could not load pattern feedback for this game. The game may have failed to analyze — try
        re-importing it.
      </p>
    );
  }
  if (isLoading || !feedback) {
    return (
      <p className="text-sm text-muted-foreground">
        Comparing this game against your recent games…
      </p>
    );
  }

  // Two distinct "nothing to say" cases, kept apart because the answer differs: too
  // little history to compare, versus a game whose player side could not be identified at
  // all (self-play, or an opponent name matching no linked username).
  if (!feedback.attributable) {
    return (
      <p className="text-sm text-muted-foreground">
        We could not tell which side you played in this game, so there is nothing to compare against
        your history.
      </p>
    );
  }
  if (!feedback.sufficient_baseline) {
    return <InsufficientHistoryNotice baselineGames={feedback.baseline_games} />;
  }

  return (
    <>
      {regenerate.isError && (
        <p className="mb-3 text-sm text-destructive">
          Could not regenerate the write-up. The comparison below is the previous one.
        </p>
      )}
      <PatternFeedbackView
        feedback={feedback}
        onRegenerate={() => regenerate.mutate()}
        isRegenerating={regenerate.isPending}
      />
    </>
  );
}
