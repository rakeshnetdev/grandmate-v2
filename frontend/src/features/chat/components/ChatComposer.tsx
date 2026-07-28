/**
 * Message input (Phase 10). Enter sends, Shift+Enter inserts a newline — the
 * conventional chat-input binding.
 */
import { useState } from 'react';
import type { KeyboardEvent } from 'react';

import { Button } from '@/shared/components/ui/button';
import { Textarea } from '@/shared/components/ui/textarea';

interface ChatComposerProps {
  onSend: (message: string) => void;
  disabled: boolean;
}

export function ChatComposer({ onSend, disabled }: ChatComposerProps) {
  const [value, setValue] = useState('');

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) {
      return;
    }
    onSend(trimmed);
    setValue('');
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  };

  return (
    <div className="flex gap-2">
      <Textarea
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask about a game, an opening, or a tactic…"
        disabled={disabled}
        className="min-h-16"
      />
      <Button type="button" onClick={submit} disabled={disabled || !value.trim()}>
        Send
      </Button>
    </div>
  );
}
