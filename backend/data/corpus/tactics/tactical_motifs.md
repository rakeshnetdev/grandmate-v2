Title: Tactical Motifs Reference
Source: GrandMate original prose (Phase 7) — see data/corpus/PROVENANCE.md for full reuse notes
Source-URL:
Licence: original
Retrieved: 2026-07-27
===

## The Pin
A pin immobilises an enemy piece by threatening to capture a more valuable piece that
sits directly behind it on the same rank, file, or diagonal. An absolute pin has the
king behind the pinned piece, so moving it would be illegal — the piece is legally
frozen. A relative pin has a lesser piece behind it (often the queen), so moving the
pinned piece is legal but usually loses material once the piece behind is captured.
Pins are most often created by a bishop, rook, or queen along a line the pinned piece
cannot leave without exposing what stands behind it.

## The Skewer
A skewer is the mirror image of a pin: the more valuable piece is attacked first and
forced to move, exposing a lesser piece standing behind it to capture. Skewers are
"absolute" when the front piece is the king — it must move, since a king cannot remain
in check — which is what makes a check-forcing skewer work even when the piece
delivering it has no material advantage over the piece behind. Long-range pieces
(bishop, rook, queen) create skewers the same way they create pins, along a shared line.

## The Fork
A fork is a single piece simultaneously attacking two or more enemy pieces, so that
defending one leaves at least one other undefended. Knights are especially effective
forkers because their L-shaped move attacks squares no other piece reaches from the
same square, but any piece — including a pawn or the king in the endgame — can fork.
A fork that hits both the king and the queen at once is called a royal fork and is
usually decisive, since the king must move and the queen is lost.

## Discovered Attack
A discovered attack happens when one piece moves out of the way of a friendly
long-range piece (bishop, rook, or queen) behind it, unmasking an attack that piece
was blocking. The moving piece is free to do anything useful on its own move —
capture, check, or create a second threat — while the newly-revealed attack lands
independently. This double-purpose nature is what makes discovered attacks
consistently strong: the opponent must answer two threats with one move.

## Double Check
A double check is a discovered attack where the moving piece itself also gives check,
so the king is attacked by two pieces at once. Because no single move can block or
capture two attackers simultaneously, a double check always forces the king to move —
it is the only response available, which makes double checks unusually forcing and a
common feature of forced mating sequences.

## Back-Rank Mate
A back-rank mate is delivered by a rook or queen along the first or eighth rank when
the defending king has no escape square, typically because its own pawns on the second
or seventh rank (f/g/h or f/c/b files depending on side) have never moved and block
every flight square. The defence — leaving one "luft" square for the king, usually by
advancing a pawn one square — is simple, which is exactly why the back-rank pattern is
worth watching for constantly rather than only in obviously sharp positions.

## Smothered Mate
A smothered mate is checkmate delivered by a knight against a king that is completely
enclosed by its own pieces, with no legal move and no way to capture or block the
knight. It typically arises from a forcing sequence (often a queen sacrifice or check)
that first drives the defending pieces into the king's own escape squares before the
knight delivers the final check.

## Hanging Piece
A hanging piece is one that is attacked and has no defender, or has fewer defenders
than attackers, so it can simply be captured for free or at a material profit. It is
the single most common way games are decided at the club level: spotting hanging
pieces, both the opponent's and one's own, is more valuable in practice than most
tactical patterns that require several precise moves to execute.

## Removing the Defender
Removing the defender (also called "undermining") wins material or breaks a position
by eliminating the piece that guards a key square or another piece, so that the
target becomes capturable once its sole protector is gone. The removal can be a
trade, a sacrifice, or a forcing move that the defender must respond to elsewhere,
as long as the net effect is that the defended piece or square is left unguarded.

## X-Ray Attack
An x-ray is when a long-range piece attacks or defends through an intervening piece —
its own or the opponent's — along the same line. It matters tactically because the
line of force is still "live": if the blocking piece moves or is captured, the x-raying
piece's influence on the square behind it becomes immediate, which is what makes some
captures unsafe even when the immediate defender count looks adequate.

## Deflection
Deflection forces a defending piece away from a square, file, or diagonal it is
guarding, usually via a sacrifice or a threat the defender cannot ignore. Once the
defender is lured elsewhere, whatever it was protecting is captured or delivered upon.
Because it usually costs material to force the defender away, deflection tactics need
engine-level verification that the follow-up genuinely recovers more than was given up.

## Decoy
A decoy is the reverse of deflection: instead of pulling a defender away, it lures an
enemy piece — often the king or queen — onto a specific square where it becomes
vulnerable to a further tactic, such as a fork, pin, or discovered attack. Decoys are
usually executed with a sacrifice that leaves the opponent little choice about which
square to move to.

## Overloading
An overloaded piece is a defender responsible for guarding two or more targets at
once. Attacking one of those targets forces the overloaded piece to choose: if it
stays to guard the target under attack, the other duty it was covering goes
undefended; if it moves to cover the other duty, the attacked target falls instead.

## Interference
Interference places a piece between an enemy defender and the piece or square it
protects, cutting the line of communication between them. Unlike a simple block, an
interference move usually offers itself as a sacrifice, so that no matter which piece
recaptures, the defensive line stays broken and the original target remains
undefended.

## Zwischenzug
A zwischenzug ("in-between move") is an unexpected intermediate move inserted before
an expected reply — most often before an expected recapture. The in-between move
poses its own threat, usually a check or an attack on a valuable piece, forcing the
opponent to deal with it first and changing the evaluation of the position before the
originally expected exchange is even completed.

## Windmill
A windmill is a repeating combination of discovered check and direct check (or
capture), most commonly executed by a rook-and-bishop or rook-and-knight pair, in
which the same discovered-check mechanism fires again and again as the attacking
piece shuttles back and forth, capturing material or delivering checks on each cycle
before the king can escape the pattern.
