/**
 * The workspace's "Story" tab (Phase 16b): the full opening/middlegame/endgame game
 * narrative, generated on demand the same way the Analysis tab's report is — thin
 * wrapper so fetch/loading/error handling stays owned by the `reports` feature's own
 * hook, matching `AnalysisTab`'s pattern.
 */
import { StoryView, useGameStory } from '@/features/reports';

interface StoryTabProps {
  gameId: string;
  profileId?: string;
}

export function StoryTab({ gameId, profileId }: StoryTabProps) {
  const { data: story, isLoading, isError } = useGameStory(gameId, profileId);

  if (isError) {
    return <p className="text-sm text-destructive">Could not load this game's story.</p>;
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
