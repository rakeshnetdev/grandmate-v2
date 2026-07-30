/**
 * The transcript for one thread (Phase 10). `grounded === false` never actually
 * reaches here — the guardrail degrades to a deterministic fallback server-side rather
 * than deliver an ungrounded answer, so there is no "this might be wrong" state to
 * render, only "generating" and the final message.
 */
import { Prose } from '@/shared/lib/prose';
import { cn } from '@/shared/lib/utils';

import type { ChatMessage } from '../api/chat';
import { CitationList } from './CitationList';

interface ChatMessageListProps {
  messages: ChatMessage[];
  pending: boolean;
}

export function ChatMessageList({ messages, pending }: ChatMessageListProps) {
  if (messages.length === 0 && !pending) {
    return <p className="text-sm text-muted-foreground">Ask a question to get started.</p>;
  }

  return (
    <div className="space-y-3">
      {messages.map((message, index) => (
        <div
          key={index}
          className={cn(
            'max-w-[85%] rounded-lg px-3 py-2 text-sm',
            message.role === 'user'
              ? 'ml-auto bg-primary text-primary-foreground'
              : 'bg-muted text-foreground',
          )}
        >
          {/* User messages are the caller's own typed text, not LLM prose — rendered
              plain rather than through markdown, so a literal "*" the user typed isn't
              reinterpreted as emphasis. */}
          {message.role === 'assistant' ? <Prose>{message.content}</Prose> : message.content}
          {message.role === 'assistant' && <CitationList citations={message.citations} />}
        </div>
      ))}
      {pending && (
        <div className="max-w-[85%] rounded-lg bg-muted px-3 py-2 text-sm text-muted-foreground">
          Thinking…
        </div>
      )}
    </div>
  );
}
