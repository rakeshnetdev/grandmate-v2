/**
 * Per-message citation transparency (Phase 16a, D-035) — surfaces `ChatCitation[]`,
 * persisted alongside each assistant message since this phase (see `domain/chat/
 * prompts.py`'s output-contract comment for the four kinds: move/evaluation/variation/
 * opening). Never shown for user messages; an assistant message with zero citations
 * renders nothing here rather than an empty "Sources" label.
 */
import { useState } from 'react';

import { cn } from '@/shared/lib/utils';

import type { ChatCitation } from '../api/chat';

function describeCitation(citation: ChatCitation): string {
  switch (citation.kind) {
    case 'move': {
      const san = typeof citation.san === 'string' ? citation.san : '?';
      const ply = typeof citation.ply === 'number' ? citation.ply : '?';
      return `Move ${ply}: ${san}`;
    }
    case 'evaluation': {
      const ply = typeof citation.ply === 'number' ? citation.ply : '?';
      const mateIn = typeof citation.mate_in === 'number' ? citation.mate_in : null;
      const evalCp = typeof citation.eval_cp === 'number' ? citation.eval_cp : null;
      const value = mateIn !== null ? `mate in ${mateIn}` : evalCp !== null ? `${evalCp}cp` : '—';
      return `Evaluation at ply ${ply}: ${value}`;
    }
    case 'variation': {
      const moves = Array.isArray(citation.moves) ? citation.moves.join(' ') : '';
      return `Line: ${moves || '—'}`;
    }
    case 'opening': {
      const name = typeof citation.opening_name === 'string' ? citation.opening_name : 'Opening';
      const eco = typeof citation.eco === 'string' ? citation.eco : '';
      return eco ? `${name} (${eco})` : name;
    }
    case 'knowledge': {
      // `title`/`source` are filled in server-side by the guardrail from the document
      // record (Phase 20) — the model only ever supplies a chunk id, so these are never
      // model-written text. A verified analysis-bucket chunk has no parent document and
      // so no title; that is expected, not a missing value.
      const title = typeof citation.title === 'string' ? citation.title : null;
      const source = typeof citation.source === 'string' ? citation.source : null;
      if (!title) {
        return 'Knowledge corpus';
      }
      return source ? `${title} — ${source}` : title;
    }
    default:
      return citation.kind;
  }
}

interface CitationListProps {
  citations: ChatCitation[];
  className?: string;
}

export function CitationList({ citations, className }: CitationListProps) {
  const [expanded, setExpanded] = useState(false);

  if (citations.length === 0) {
    return null;
  }

  return (
    <div className={cn('mt-1', className)}>
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground"
      >
        {expanded ? 'Hide' : 'Show'} {citations.length} source{citations.length === 1 ? '' : 's'}
      </button>
      {expanded && (
        <ul className="mt-1 space-y-0.5 border-l-2 border-border pl-2 text-xs text-muted-foreground">
          {citations.map((citation, index) => (
            <li key={index} className="font-mono">
              {describeCitation(citation)}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
