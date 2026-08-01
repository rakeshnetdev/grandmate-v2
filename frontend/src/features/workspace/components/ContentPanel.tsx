/**
 * The workspace's middle panel (Phase 16a, D-035): tabbed content instead of one long
 * scroll. "Overview" and "Learning" are profile-level, so they are always available;
 * "Analysis"/"Moves"/"Patterns"/"Story" only make sense once a game is selected, so those
 * tabs don't exist at all until then, rather than existing-but-disabled.
 */
import type { TabItem } from '@/shared/components/ui/tabs';
import { Tabs } from '@/shared/components/ui/tabs';

import { AnalysisTab } from './AnalysisTab';
import { LearningTab } from './LearningTab';
import { MovesTab } from './MovesTab';
import { OverviewTab } from './OverviewTab';
import { PatternsTab } from './PatternsTab';
import { StoryTab } from './StoryTab';

export type ContentTab = 'overview' | 'learning' | 'analysis' | 'moves' | 'patterns' | 'story';

const GAME_TABS: TabItem[] = [
  { value: 'overview', label: 'Overview' },
  { value: 'learning', label: 'Learning' },
  { value: 'analysis', label: 'Analysis' },
  { value: 'moves', label: 'Moves' },
  { value: 'patterns', label: 'Patterns' },
  { value: 'story', label: 'Story' },
];
const NO_GAME_TABS: TabItem[] = [
  { value: 'overview', label: 'Overview' },
  { value: 'learning', label: 'Learning' },
];

const PROFILE_LEVEL_TABS: ContentTab[] = ['overview', 'learning'];

interface ContentPanelProps {
  profileId?: string;
  selectedGameId?: string;
  tab: ContentTab;
  onTabChange: (tab: ContentTab) => void;
}

export function ContentPanel({ profileId, selectedGameId, tab, onTabChange }: ContentPanelProps) {
  // A game-scoped tab (e.g. "moves") is meaningless once no game is selected — fall back
  // to Overview rather than rendering a tab with nothing to show. Profile-level tabs
  // survive deselection, since they never depended on the game.
  const activeTab = selectedGameId || PROFILE_LEVEL_TABS.includes(tab) ? tab : 'overview';

  return (
    <div className="flex h-full flex-col">
      <Tabs
        items={selectedGameId ? GAME_TABS : NO_GAME_TABS}
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
      </div>
    </div>
  );
}
