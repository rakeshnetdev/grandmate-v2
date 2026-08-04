/**
 * The workspace's "Story" tab (Phase 16b): the full opening/middlegame/endgame game
 * narrative, generated on demand the same way the Analysis tab's report is — thin
 * wrapper so fetch/loading/error handling stays owned by the `reports` feature's own
 * hook, matching `AnalysisTab`'s pattern.
 */
import {
  AnalyzingNotice,
  StoryView,
  isAnalysisPending,
  useGameStory,
  useRegenerateGameStory,
} from '@/features/reports';
import { RegenerateButton } from '@/shared/components/ui/regenerate-button';

interface StoryTabProps {
  gameId: string;
  profileId?: string;
}

export function StoryTab({ gameId, profileId }: StoryTabProps) {
  const {
    data: story,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useGameStory(gameId, profileId);
  const regenerate = useRegenerateGameStory(gameId, profileId);

  // Same distinction the persona report makes: a game whose engine analysis has not
  // finished is pending, not broken.
  if (isAnalysisPending(error)) {
    return <AnalyzingNotice gameId={gameId} />;
  }
  if (isError) {
    // No story means no badge to hang the refresh control off, so it goes beside the
    // error instead — see `PersonaReportPanel`'s error branch for why this retries
    // rather than regenerates.
    return (
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm text-destructive">
          Could not load this game&apos;s story. The game may have failed to analyze — try
          re-importing it.
        </p>
        <RegenerateButton
          onClick={() => void refetch()}
          label="story"
          isBusy={isFetching}
          className="text-destructive hover:text-destructive"
        />
      </div>
    );
  }
  if (isLoading || !story) {
    return (
      <p className="text-sm text-muted-foreground">
        Writing the full game story — this can take a few seconds…
      </p>
    );
  }
  return (
    <>
      {regenerate.isError && (
        <p className="mb-3 text-sm text-destructive">
          Could not regenerate the story. The one below is the previous version.
        </p>
      )}
      <StoryView
        report={story}
        onRegenerate={() => regenerate.mutate()}
        isRegenerating={regenerate.isPending}
      />
    </>
  );
}
