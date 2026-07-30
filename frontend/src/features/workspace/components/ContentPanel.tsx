/**
 * The workspace's middle panel (Phase 16a, D-035): tabbed content instead of one long
 * scroll. "Overview" is always available (profile-level analytics/training plan);
 * "Analysis"/"Moves"/"Patterns" only make sense once a game is selected, so those tabs
 * don't exist at all until then, rather than existing-but-disabled.
 */
import type { TabItem } from '@/shared/components/ui/tabs';
import { Tabs } from '@/shared/components/ui/tabs';

import { AnalysisTab } from './AnalysisTab';
import { MovesTab } from './MovesTab';
import { OverviewTab } from './OverviewTab';
import { PatternsTab } from './PatternsTab';
import { PgnTab } from './PgnTab';
import { StoryTab } from './StoryTab';

export type ContentTab = 'overview' | 'analysis' | 'moves' | 'patterns' | 'story' | 'pgn';

const GAME_TABS: TabItem[] = [
  { value: 'overview', label: 'Overview' },
  { value: 'analysis', label: 'Analysis' },
  { value: 'moves', label: 'Moves' },
  { value: 'patterns', label: 'Patterns' },
  { value: 'story', label: 'Story' },
  { value: 'pgn', label: 'PGN' },
];
const NO_GAME_TABS: TabItem[] = [{ value: 'overview', label: 'Overview' }];

interface ContentPanelProps {
  profileId?: string;
  selectedGameId?: string;
  tab: ContentTab;
  onTabChange: (tab: ContentTab) => void;
}

export function ContentPanel({ profileId, selectedGameId, tab, onTabChange }: ContentPanelProps) {
  // A tab from a previous game selection (e.g. "moves") is meaningless once no game is
  // selected — fall back to Overview rather than rendering a tab with nothing to show.
  const activeTab = selectedGameId ? tab : 'overview';

  return (
    <div className="flex h-full flex-col">
      <Tabs
        items={selectedGameId ? GAME_TABS : NO_GAME_TABS}
        value={activeTab}
        onChange={(value) => onTabChange(value as ContentTab)}
      />
      <div className="flex-1 overflow-y-auto p-4">
        {activeTab === 'overview' && <OverviewTab profileId={profileId} />}
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
        {activeTab === 'pgn' && selectedGameId && (
          <PgnTab gameId={selectedGameId} profileId={profileId} />
        )}
      </div>
    </div>
  );
}
