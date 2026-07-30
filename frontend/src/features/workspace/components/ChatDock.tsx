/**
 * The workspace's right-hand panel (Phase 16a, D-035, D-035 scope decision 4): chat and
 * memory as two tabs of the same docked panel, not separate pages — memory is what the
 * assistant remembers about the profile, chat-adjacent by nature.
 */
import { useState } from 'react';

import { ChatPanel } from '@/features/chat';
import { MemoryPanel } from '@/features/memory';
import { Tabs } from '@/shared/components/ui/tabs';

const DOCK_TABS = [
  { value: 'chat', label: 'Chat' },
  { value: 'memory', label: 'Memory' },
];

interface ChatDockProps {
  profileId?: string;
  /** Pre-seeds a new thread's context when opened from a selected game. */
  activeGameId?: string;
}

export function ChatDock({ profileId, activeGameId }: ChatDockProps) {
  const [dockTab, setDockTab] = useState<'chat' | 'memory'>('chat');
  const [selectedThreadId, setSelectedThreadId] = useState<string>();

  return (
    <div className="flex h-full flex-col">
      <Tabs
        items={DOCK_TABS}
        value={dockTab}
        onChange={(value) => setDockTab(value as 'chat' | 'memory')}
      />
      <div className="flex-1 overflow-y-auto p-4">
        {dockTab === 'chat' ? (
          <ChatPanel
            profileId={profileId}
            activeGameId={activeGameId}
            selectedThreadId={selectedThreadId}
            onSelectThread={setSelectedThreadId}
          />
        ) : (
          <MemoryPanel profileId={profileId} />
        )}
      </div>
    </div>
  );
}
