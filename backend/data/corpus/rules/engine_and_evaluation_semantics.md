Title: Engine and Evaluation Semantics
Source: GrandMate original prose (Phase 7) — see data/corpus/PROVENANCE.md for full reuse notes
Source-URL:
Licence: original
Retrieved: 2026-07-27
===

## UCI Move Notation
UCI (Universal Chess Interface) is the protocol chess engines use to communicate, and
it represents a move as a start square followed by an end square — for example
`e2e4` rather than the algebraic `e4`. A promotion appends the piece letter, e.g.
`e7e8q` for promoting to a queen. Every move this system's engine analysis produces
or evaluates is expressed this way internally, even though a report shown to a user
is always translated back to standard algebraic notation.

## Centipawn Evaluation
Engine evaluation is expressed in centipawns, one hundredth of the value of a pawn,
so that fractional advantages can be compared precisely. A positive number favours
White and a negative number favours Black; roughly speaking, +100 centipawns is
"about a pawn ahead," though the practical significance of a given centipawn value
depends heavily on how much material and how many pieces remain on the board. A
mate score (commonly written as M-in-N) overrides the centipawn scale entirely: it
means a forced checkmate exists in N moves and is not a magnitude to be averaged or
compared numerically against a centipawn value.

## Evaluation Swing and Move Classification
An eval swing is the change in evaluation caused by a single move, measured from the
mover's own perspective (a move that helps the mover produces a positive swing; one
that hurts them produces a negative one). This system classifies each move —
`best`, `good`, `inaccuracy`, `mistake`, or `blunder` — based on how much evaluation
was lost compared to the engine's own top choice at that position, with the exact
centipawn thresholds for each label configured rather than fixed in code, since
reasonable thresholds can vary by time control and player strength.

## Search Depth and Analysis Tiers
Search depth is how many half-moves (plies) ahead the engine calculates before
settling on an evaluation; deeper search generally produces a more accurate and more
stable evaluation, at a proportional cost in computation time. This system runs a
fast baseline pass at a lower depth across every move of a game, then re-analyses
only the handful of moves flagged as critical — large swings, or a position moving
from winning to non-winning — at a much deeper search, since spending the deepest
search on every single move in a game would be wasteful when most moves are not
where a game is actually decided.

## Principal Variation
The principal variation (PV) is the sequence of moves the engine considers best
from a given position, for both sides, not just the immediate best move. A PV is
useful for explaining *why* a move is good or bad: it shows the concrete line of
play the evaluation is based on, rather than asserting a verdict with no visible
reasoning behind it.
