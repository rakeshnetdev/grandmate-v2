/**
 * The workspace's left panel (Phase 16a, D-035): every loaded game for the active
 * profile, click-to-select rather than navigation (unlike the retired `GamesList`,
 * which linked to a separate game-detail route — selection here just updates the
 * workspace's own `game` URL param). Collapsible to an icon rail so the middle/right
 * panels can reclaim the width when a reader just wants to focus on one game.
 */
import { ChevronLeft, ChevronRight, Plus } from 'lucide-react';
import { useState } from 'react';

import { opponentLine, useGames } from '@/features/games';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/lib/utils';

import { ImportModal } from './ImportModal';

interface GameListPanelProps {
  profileId?: string;
  selectedGameId?: string;
  onSelectGame: (gameId: string) => void;
  collapsed: boolean;
  onToggleCollapsed: () => void;
}

export function GameListPanel({
  profileId,
  selectedGameId,
  onSelectGame,
  collapsed,
  onToggleCollapsed,
}: GameListPanelProps) {
  const { data: games, isLoading } = useGames(profileId);
  const [importOpen, setImportOpen] = useState(false);

  if (collapsed) {
    return (
      <div className="flex h-full flex-col items-center gap-2 border-r border-border py-3">
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label="Expand game list"
          onClick={onToggleCollapsed}
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label="Import games"
          onClick={() => setImportOpen(true)}
        >
          <Plus className="h-4 w-4" />
        </Button>
        <ImportModal open={importOpen} onClose={() => setImportOpen(false)} profileId={profileId} />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col border-r border-border">
      <div className="flex items-center justify-between gap-2 border-b border-border p-3">
        <h2 className="text-sm font-semibold">Games</h2>
        <div className="flex items-center gap-1">
          <Button type="button" size="sm" onClick={() => setImportOpen(true)}>
            <Plus className="h-4 w-4" />
            Import
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label="Collapse game list"
            onClick={onToggleCollapsed}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-2">
        {isLoading ? (
          <p className="p-2 text-sm text-muted-foreground">Loading games…</p>
        ) : !games || games.length === 0 ? (
          <p className="p-2 text-sm text-muted-foreground">
            No games imported yet. Use Import to get started.
          </p>
        ) : (
          <ul className="space-y-1">
            {games.map((game) => (
              <li key={game.id}>
                <button
                  type="button"
                  onClick={() => onSelectGame(game.id)}
                  className={cn(
                    'w-full rounded-md px-3 py-2 text-left text-sm hover:bg-accent',
                    game.id === selectedGameId && 'bg-accent font-medium',
                  )}
                >
                  <span className="block truncate">{opponentLine(game.headers)}</span>
                  {!game.canonicalized_at && (
                    <span className="text-xs text-muted-foreground">Not parsed</span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <ImportModal open={importOpen} onClose={() => setImportOpen(false)} profileId={profileId} />
    </div>
  );
}
