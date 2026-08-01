/**
 * Bulleted lists that use chess pieces as the marker.
 *
 * Used by the story report and the training plan so their prose reads as a set of points
 * to act on rather than a stack of bordered boxes. The piece is decoration with a job:
 * it makes a long generated paragraph scannable, and it keeps the surface feeling like
 * chess rather than a form.
 *
 * The solid (conventionally "black") glyphs are used deliberately — the outline glyphs
 * ♙♘♗♖♕♔ render as thin hollow shapes that all but disappear against a light background
 * in several common system fonts. Colour comes from the class, not the glyph.
 *
 * Markers are `aria-hidden`: a screen reader announcing "black chess knight" before each
 * point is noise, and the list semantics already convey that these are items.
 */
import type { ReactNode } from 'react';

import { cn } from '@/shared/lib/utils';

export const CHESS_PIECE = {
  pawn: '♟',
  knight: '♞',
  bishop: '♝',
  rook: '♜',
  queen: '♛',
  king: '♚',
} as const;

export type ChessPiece = keyof typeof CHESS_PIECE;

interface PieceListProps {
  className?: string;
  children: ReactNode;
}

export function PieceList({ className, children }: PieceListProps) {
  return <ul className={cn('space-y-2', className)}>{children}</ul>;
}

interface PieceListItemProps {
  piece: ChessPiece;
  /** Marker colour. Defaults to a muted foreground so the text stays the focus. */
  tone?: string;
  children: ReactNode;
}

export function PieceListItem({ piece, tone, children }: PieceListItemProps) {
  return (
    <li className="flex items-start gap-2.5">
      <span
        aria-hidden="true"
        className={cn(
          'mt-px shrink-0 select-none text-base leading-6',
          tone ?? 'text-foreground/40',
        )}
      >
        {CHESS_PIECE[piece]}
      </span>
      <div className="min-w-0 flex-1">{children}</div>
    </li>
  );
}
