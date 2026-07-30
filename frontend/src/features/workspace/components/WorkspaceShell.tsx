/**
 * The three-panel workspace shell (Phase 16a, D-035) — the single post-login surface
 * that replaces the former Import/Games/Dashboard/Chat/Memory/Game-Detail pages. State
 * lives in the URL (`profile`/`game`/`tab` search params) wherever a reader would want
 * to bookmark or share a specific view, same convention `DashboardPage`/`GameDetailPage`
 * already used — this is a consolidation of those pages' own state, not a new pattern.
 *
 * Responsive (Phase 16a): both side panels are always visible from `lg:` up. Below
 * that, neither this app nor the sibling `grandmate/` reference ever solved mobile
 * navigation — here the left panel becomes an off-canvas drawer and the right (chat)
 * panel becomes a full-height overlay, each toggled from a small mobile-only toolbar.
 */
import { MessageSquare, PanelLeft } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import { ProfileToggle } from '@/features/profiles';
import { Button } from '@/shared/components/ui/button';

import { useLeftPanelCollapsed } from '../hooks/useLeftPanelCollapsed';
import type { ContentTab } from './ContentPanel';
import { ContentPanel } from './ContentPanel';
import { ChatDock } from './ChatDock';
import { GameListPanel } from './GameListPanel';

const VALID_TABS: ContentTab[] = ['overview', 'analysis', 'moves', 'patterns', 'story', 'pgn'];

function parseTab(value: string | null): ContentTab {
  return VALID_TABS.includes(value as ContentTab) ? (value as ContentTab) : 'overview';
}

export function WorkspaceShell() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [leftCollapsed, toggleLeftCollapsed] = useLeftPanelCollapsed();
  const [mobileLeftOpen, setMobileLeftOpen] = useState(false);
  const [mobileRightOpen, setMobileRightOpen] = useState(false);

  const profileId = searchParams.get('profile') ?? undefined;
  const selectedGameId = searchParams.get('game') ?? undefined;
  const tab = parseTab(searchParams.get('tab'));

  function updateParams(next: Record<string, string | undefined>) {
    const params = new URLSearchParams(searchParams);
    for (const [key, value] of Object.entries(next)) {
      if (value === undefined) {
        params.delete(key);
      } else {
        params.set(key, value);
      }
    }
    setSearchParams(params);
  }

  function handleProfileChange(nextProfileId: string | undefined) {
    // Switching profiles invalidates whatever game/tab was selected in the old one.
    updateParams({ profile: nextProfileId, game: undefined, tab: undefined });
  }

  function handleSelectGame(gameId: string) {
    updateParams({ game: gameId, tab: 'analysis' });
    setMobileLeftOpen(false);
  }

  function handleTabChange(nextTab: ContentTab) {
    updateParams({ tab: nextTab });
  }

  // Escape closes whichever mobile overlay is open — `Dialog` (the import modal)
  // already does this itself; these two hand-rolled overlays need the same behaviour
  // wired explicitly since they aren't built on that shared primitive.
  useEffect(() => {
    if (!mobileLeftOpen && !mobileRightOpen) {
      return;
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setMobileLeftOpen(false);
        setMobileRightOpen(false);
      }
    }
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [mobileLeftOpen, mobileRightOpen]);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between gap-3 border-b border-border p-3">
        <ProfileToggle value={profileId} onChange={handleProfileChange} />
        <div className="flex items-center gap-1 lg:hidden">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label="Show games"
            onClick={() => setMobileLeftOpen(true)}
          >
            <PanelLeft className="h-4 w-4" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label="Show chat"
            onClick={() => setMobileRightOpen(true)}
          >
            <MessageSquare className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        <div
          className={
            leftCollapsed ? 'hidden w-14 shrink-0 lg:block' : 'hidden w-72 shrink-0 lg:block'
          }
        >
          <GameListPanel
            profileId={profileId}
            selectedGameId={selectedGameId}
            onSelectGame={handleSelectGame}
            collapsed={leftCollapsed}
            onToggleCollapsed={toggleLeftCollapsed}
          />
        </div>

        <div className="min-w-0 flex-1">
          <ContentPanel
            profileId={profileId}
            selectedGameId={selectedGameId}
            tab={tab}
            onTabChange={handleTabChange}
          />
        </div>

        <div className="hidden w-96 shrink-0 border-l border-border lg:block">
          <ChatDock profileId={profileId} activeGameId={selectedGameId} />
        </div>
      </div>

      {mobileLeftOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            type="button"
            aria-label="Close"
            className="absolute inset-0 bg-background/80 backdrop-blur-sm"
            onClick={() => setMobileLeftOpen(false)}
          />
          <div className="absolute top-0 left-0 h-full w-72 bg-background shadow-lg">
            <GameListPanel
              profileId={profileId}
              selectedGameId={selectedGameId}
              onSelectGame={handleSelectGame}
              collapsed={false}
              onToggleCollapsed={() => setMobileLeftOpen(false)}
            />
          </div>
        </div>
      )}

      {mobileRightOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            type="button"
            aria-label="Close"
            className="absolute inset-0 bg-background/80 backdrop-blur-sm"
            onClick={() => setMobileRightOpen(false)}
          />
          <div className="absolute top-0 right-0 flex h-full w-full max-w-sm flex-col bg-background shadow-lg">
            <div className="flex items-center justify-end border-b border-border p-2">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setMobileRightOpen(false)}
              >
                Close
              </Button>
            </div>
            <div className="flex-1 overflow-hidden">
              <ChatDock profileId={profileId} activeGameId={selectedGameId} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
