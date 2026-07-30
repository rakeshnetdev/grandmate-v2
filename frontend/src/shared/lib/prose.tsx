/**
 * Markdown + chess-notation-aware rendering for LLM prose (Phase 16a, D-035).
 *
 * Two separate concerns, deliberately not one regex pass over raw text the way the
 * sibling `grandmate/` frontend's `highlightChessKeywords` worked (duplicated across two
 * files, and run *before* markdown structure existed, so its own bold-marker handling
 * had to half-reimplement what a real parser already does correctly):
 *
 * 1. `react-markdown` (+ `remark-gfm` for lists/bold/strikethrough) parses markdown
 *    structure properly — this is the actual fix for "prose renders as literal
 *    asterisks."
 * 2. `highlightChessNotation` then runs *after* parsing, only against already-resolved
 *    text runs (a paragraph's or list item's direct string content) via `components`
 *    overrides — so it only ever has to recognise chess tokens in plain text, never
 *    fight markdown syntax for the same characters.
 *
 * Nested inline content (e.g. text inside a `**bold**` span within a paragraph) is not
 * re-highlighted — `renderChildren` only processes direct string children, not other
 * elements' own children. Rare in practice for this app's prose (short paragraphs, flat
 * lists) and a reasonable place to stop rather than writing a full recursive AST walker
 * for a cosmetic feature.
 */
import type { ComponentProps, ReactNode } from 'react';
import { Fragment } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { CLASSIFICATION_BADGE_CLASS } from './classification';
import { cn } from './utils';

type HighlightKind = 'move' | 'blunder' | 'mistake' | 'inaccuracy' | 'best';

const HIGHLIGHT_CLASS: Record<HighlightKind, string> = {
  move: 'bg-muted text-foreground border-border font-mono',
  blunder: CLASSIFICATION_BADGE_CLASS.blunder,
  mistake: CLASSIFICATION_BADGE_CLASS.mistake,
  inaccuracy: CLASSIFICATION_BADGE_CLASS.inaccuracy,
  best: CLASSIFICATION_BADGE_CLASS.best,
};

// SAN moves: castling, or [piece][disambiguation]?[capture]?[destination][promotion]?
// [check/mate]? — e.g. "e4", "Nf3", "Rxe8+", "O-O", "e8=Q#". Requires a real
// file+rank pair, so it does not fire on arbitrary two-character words.
const HIGHLIGHT_RE =
  /(?<move>\b(?:O-O-O|O-O|[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?)\b)|(?<blunder>\bblunders?\b)|(?<mistake>\bmistakes?\b)|(?<inaccuracy>\binaccurac(?:y|ies)\b)|(?<best>\b(?:brilliant|excellent)\b)/gi;

function highlightChessNotation(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let lastIndex = 0;
  let matchIndex = 0;

  for (const match of text.matchAll(HIGHLIGHT_RE)) {
    const start = match.index;
    if (start > lastIndex) {
      nodes.push(text.slice(lastIndex, start));
    }
    const kind = (Object.entries(match.groups ?? {}).find(([, v]) => v !== undefined)?.[0] ??
      'move') as HighlightKind;
    nodes.push(
      <span
        key={`${keyPrefix}-${matchIndex}`}
        className={cn(
          'rounded border px-1 py-0.5 text-[0.9em] font-semibold',
          HIGHLIGHT_CLASS[kind],
        )}
      >
        {match[0]}
      </span>,
    );
    lastIndex = start + match[0].length;
    matchIndex += 1;
  }
  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }
  return nodes;
}

function renderChildren(children: ReactNode, keyPrefix: string): ReactNode {
  const items = Array.isArray(children) ? children : [children];
  return items.map((child, index) =>
    typeof child === 'string' ? (
      <Fragment key={`${keyPrefix}-${index}`}>
        {highlightChessNotation(child, `${keyPrefix}-${index}`)}
      </Fragment>
    ) : (
      <Fragment key={`${keyPrefix}-${index}`}>{child}</Fragment>
    ),
  );
}

const markdownComponents: ComponentProps<typeof ReactMarkdown>['components'] = {
  p: ({ children }) => <p className="mb-2 last:mb-0">{renderChildren(children, 'p')}</p>,
  li: ({ children }) => <li>{renderChildren(children, 'li')}</li>,
  ul: ({ children }) => <ul className="list-inside list-disc space-y-1">{children}</ul>,
  ol: ({ children }) => <ol className="list-inside list-decimal space-y-1">{children}</ol>,
  strong: ({ children }) => (
    <strong className="font-semibold">{renderChildren(children, 'strong')}</strong>
  ),
  em: ({ children }) => <em>{renderChildren(children, 'em')}</em>,
  code: ({ children }) => (
    <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.9em]">{children}</code>
  ),
  a: ({ children, href }) => (
    <a href={href} className="underline underline-offset-2" target="_blank" rel="noreferrer">
      {children}
    </a>
  ),
};

interface ProseProps {
  children: string;
  className?: string;
}

/** Renders LLM-generated markdown prose with chess-notation-aware highlighting —
 * chat answers, report findings/recommendations, training-plan text. */
export function Prose({ children, className }: ProseProps) {
  return (
    <div className={cn('text-sm leading-relaxed', className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
        {children}
      </ReactMarkdown>
    </div>
  );
}
