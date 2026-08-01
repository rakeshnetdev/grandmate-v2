/**
 * The workspace's "Story" tab (Phase 16b): the full opening/middlegame/endgame game
 * narrative, generated on demand the same way the Analysis tab's report is — thin
 * wrapper so fetch/loading/error handling stays owned by the `reports` feature's own
 * hook, matching `AnalysisTab`'s pattern.
 */
import { AnalyzingNotice, StoryView, isAnalysisPending, useGameStory } from '@/features/reports';

interface StoryTabProps {
  gameId: string;
  profileId?: string;
}

export function StoryTab({ gameId, profileId }: StoryTabProps) {
  const { data: story, isLoading, isError, error } = useGameStory(gameId, profileId);

  // Same distinction the persona report makes: a game whose engine analysis has not
  // finished is pending, not broken.
  if (isAnalysisPending(error)) {
    return <AnalyzingNotice gameId={gameId} />;
  }
  if (isError) {
    return (
      <p className="text-sm text-destructive">
        Could not load this game&apos;s story. The game may have failed to analyze — try
        re-importing it.
      </p>
    );
  }
  if (isLoading || !story) {
    return (
      <p className="text-sm text-muted-foreground">
        Writing the full game story — this can take a few seconds…
      </p>
    );
  }
  return <StoryView report={story} />;
}
