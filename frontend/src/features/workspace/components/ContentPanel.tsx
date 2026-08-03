/**
 * The workspace's middle panel (Phase 16a, D-035): tabbed content instead of one long
 * scroll. "Overview" and "Learning" are profile-level, so they are always available;
 * "Analysis"/"Moves"/"Patterns"/"Story"/"Pattern feedback" only make sense once a game is
 * selected, so those tabs don't exist at all until then, rather than existing-but-disabled.
 *
 * "Moves" and "Patterns" are gated a second time behind `showEngineAnalysis` — the raw
 * engine detail is opt-in, see `useShowEngineAnalysis`. Same treatment as the game gate:
 * the tabs are absent rather than disabled, and an active-but-now-hidden tab falls back
 * to Overview instead of leaving the strip with nothing selected.
 */
import type { TabItem } from '@/shared/components/ui/tabs';
import { Tabs } from '@/shared/components/ui/tabs';

import { AnalysisTab } from './AnalysisTab';
import { LearningTab } from './LearningTab';
import { MovesTab } from './MovesTab';
import { OverviewTab } from './OverviewTab';
import { PatternFeedbackTab } from './PatternFeedbackTab';
import { PatternsTab } from './PatternsTab';
import { StoryTab } from './StoryTab';

export type ContentTab =
  'overview' | 'learning' | 'analysis' | 'moves' | 'patterns' | 'story' | 'pattern-feedback';

// Ordered by how a reader works through a game: the coaching read first (Analysis, then
// how it compares to their recent history, then the narrative), and the raw engine detail
// last — which also puts the two `showEngineAnalysis`-gated tabs at the end, so hiding
// them never leaves a gap in the middle of the strip.
const GAME_TABS: TabItem[] = [
  { value: 'overview', label: 'Overview' },
  { value: 'learning', label: 'Learning' },
  { value: 'analysis', label: 'Analysis' },
  // Phase 19: the only tab that reads across games — everything around it describes this
  // game alone.
  { value: 'pattern-feedback', label: 'Pattern feedback' },
  { value: 'story', label: 'Story' },
  { value: 'moves', label: 'Moves' },
  { value: 'patterns', label: 'Patterns' },
];
const NO_GAME_TABS: TabItem[] = [
  { value: 'overview', label: 'Overview' },
  { value: 'learning', label: 'Learning' },
];

const PROFILE_LEVEL_TABS: ContentTab[] = ['overview', 'learning'];

// The tabs that show the engine's own output, hidden unless the reader asks for them.
const ENGINE_ANALYSIS_TABS: ContentTab[] = ['moves', 'patterns'];

interface ContentPanelProps {
  profileId?: string;
  selectedGameId?: string;
  tab: ContentTab;
  onTabChange: (tab: ContentTab) => void;
  showEngineAnalysis: boolean;
}

export function ContentPanel({
  profileId,
  selectedGameId,
  tab,
  onTabChange,
  showEngineAnalysis,
}: ContentPanelProps) {
  const gameTabs = showEngineAnalysis
    ? GAME_TABS
    : GAME_TABS.filter((item) => !ENGINE_ANALYSIS_TABS.includes(item.value as ContentTab));

  // A tab is available when its prerequisites hold: a game-scoped tab (e.g. "moves")
  // needs a selected game, and an engine tab needs the toggle on. Anything else falls
  // back to Overview rather than rendering a tab strip with nothing selected — reachable
  // from a bookmarked `?tab=moves` URL as much as from toggling engine analysis off
  // while standing on one of those tabs.
  const available =
    (Boolean(selectedGameId) || PROFILE_LEVEL_TABS.includes(tab)) &&
    (showEngineAnalysis || !ENGINE_ANALYSIS_TABS.includes(tab));
  const activeTab = available ? tab : 'overview';

  return (
    <div className="flex h-full flex-col">
      <Tabs
        items={selectedGameId ? gameTabs : NO_GAME_TABS}
        value={activeTab}
        onChange={(value) => onTabChange(value as ContentTab)}
      />
      <div className="flex-1 overflow-y-auto p-4">
        {activeTab === 'overview' && <OverviewTab profileId={profileId} />}
        {activeTab === 'learning' && <LearningTab profileId={profileId} />}
        {activeTab === 'analysis' && selectedGameId && (
          <AnalysisTab gameId={selectedGameId} profileId={profileId} />
        )}
        {activeTab === 'moves' && selectedGameId && (
          <MovesTab gameId={selectedGameId} profileId={profileId} />
        )}
        {activeTab === 'patterns' && selectedGameId && (
          <PatternsTab gameId={selectedGameId} profileId={profileId} />
        )}
        {activeTab === 'story' && selectedGameId && (
          <StoryTab gameId={selectedGameId} profileId={profileId} />
        )}
        {activeTab === 'pattern-feedback' && selectedGameId && (
          <PatternFeedbackTab gameId={selectedGameId} profileId={profileId} />
        )}
      </div>
    </div>
  );
}
