# Domain Glossary and Starter Taxonomies

Shared vocabulary for GrandMate v2. Terms here are used consistently in code, schemas,
prompts, and documentation. If code and this document disagree, one of them is a bug.

---

## Chess terms

| Term | Meaning in this system |
|------|------------------------|
| **Ply** | A single move by one side. A full move by both sides is two plies. Move numbering in the UI is by full move; internal indexing is by ply. |
| **FEN** | Forsyth–Edwards Notation. Full position state including halfmove clock and fullmove number. |
| **EPD** | Extended Position Description. A FEN without the move counters. Used as the opening lookup key because it identifies a position independently of the move order that reached it. |
| **PV** | Principal variation. The engine's best line from a position. |
| **Centipawn (cp)** | One hundredth of a pawn. The unit of engine evaluation. |
| **Eval swing** | The change in evaluation caused by a move, measured as eval-before minus eval-after from the mover's perspective. |
| **Critical moment** | A ply where the eval swing exceeds a threshold, or where the position was winning and became non-winning. The candidate set for deep re-analysis. |
| **ECO** | Encyclopaedia of Chess Openings classification code, A00–E99. |
| **Time control** | Bullet, blitz, rapid, classical, correspondence. Segmentation dimension for aggregates. |

## System terms

| Term | Meaning |
|------|---------|
| **Canonical Game Object** | The single enriched object produced per game. Truth level 1. |
| **Profile Aggregate** | Rolled-up patterns across a window of games. Truth level 2. |
| **Persona View** | A rendering of levels 1 and 2 for a particular audience. Truth level 3. |
| **Profile** | A player identity within the system. May be the account owner's own, a linked student or child, or an observed opponent. |
| **Role** | The relationship a user has to a profile: owner, coach, parent, viewer, student. Governs permission. |
| **Persona** | The presentation mode used to render output: self-learner, coach, kid. Governs tone and depth. Orthogonal to role. |
| **Window** | The set of games an aggregate covers, e.g. last 30 games. |
| **Bucket** | One partition of the knowledge corpus with its own chunking and retrieval strategy. |
| **Grounding** | The property that every factual claim in an answer traces to a deterministic analysis record or a retrieved corpus chunk. |
| **Golden set** | A human-reviewed evaluation dataset. Authoritative. |
| **Synthetic set** | A generated evaluation dataset. Useful for coverage, never authoritative on its own. |

## Role vs persona

These are separate concepts and must not be merged.

- A **coach** (role) may view a student's profile using the **kid** persona to prepare
  language they will use in a lesson.
- A **parent** (role) viewing a child profile is not automatically served the **kid**
  persona; they may prefer the coach persona's detail.

Role answers "may this user see this data". Persona answers "how should it be worded".
Conflating them means a permission change silently alters tone, or a tone change silently
alters permission. Both are bad.

---

## Starter tactical motif taxonomy

Sixteen motifs for Phase 6 detectors. Seeded from the reference app's tactics notes, which
are well written and reusable. Each motif needs a detector, a curated positive test set,
and a false-positive review set before it ships.

| Motif | Detection difficulty | Notes |
|-------|---------------------|-------|
| Fork | Low | One piece attacking two or more valuable targets. Most reliable detector. |
| Pin | Low | Absolute (against king) and relative variants tracked separately. |
| Skewer | Low | Inverse pin; high-value piece forced to move exposing a lesser one behind. |
| Discovered attack | Medium | Requires tracking the unmasked line, not just the moved piece. |
| Double check | Low | Mechanically detectable from check count. |
| Back-rank mate | Low | Pattern is highly constrained. |
| Smothered mate | Low | Knight mate with all king escape squares occupied by friendly pieces. |
| Hanging piece | Low | Undefended and attacked. High frequency, high coaching value. |
| Removing the defender | Medium | Requires defender-relationship modelling. |
| Deflection | High | Intent-laden; needs engine corroboration to avoid false positives. |
| Decoy | High | Same caveat as deflection. |
| Overloading | High | Needs multi-target defensive duty analysis. |
| Interference | High | Rare; low priority. |
| X-ray | Medium | Line-through-piece attack or defence. |
| Zwischenzug | High | Requires expectation modelling of the "normal" move. |
| Windmill | High | Rare. Ship last or not at all. |

Sequencing note: build the low-difficulty detectors first and hold the high-difficulty
ones behind engine corroboration. A confident wrong motif label is worse than no label,
because it teaches the user something false.

## Starter strategic theme taxonomy

Ten themes for Phase 6. These are slower-moving positional properties rather than
move-level tactics, and most are computed over a span of plies rather than at one.

| Theme | Signal |
|-------|--------|
| Weak king safety | King exposure metrics, missing pawn shield, open files toward the king |
| Pawn structure damage | Doubled, isolated, or backward pawns created |
| Passed pawn creation | Passed pawn appears and persists |
| Piece activity imbalance | Aggregate mobility differential sustained over plies |
| Bad bishop | Bishop blocked by own fixed pawns on its colour |
| Open file control | Rook or queen occupying an open or half-open file |
| Centre control | Occupation and attack counts on the central squares |
| Space advantage | Advanced pawn chain and territory differential |
| Development lag | Undeveloped minor pieces past the opening phase |
| Time trouble collapse | Accuracy dropping sharply in the final phase where clock data exists |

## Training theme mapping

Detected motifs and themes map to coachable themes. This mapping is the bridge from
analysis to recommendation and lives in `domain/patterns`, not in prompts.

| Finding | Training theme |
|---------|----------------|
| Repeated hanging pieces | Blunder-check discipline |
| Repeated missed forks | Tactical pattern drilling |
| Development lag | Opening principles |
| Weak king safety | King safety and castling timing |
| Pawn structure damage | Structural decision-making |
| Time trouble collapse | Clock management |
| Opening-family underperformance | Repertoire review for that family |

## Move classification vocabulary

| Label | Rule |
|-------|------|
| `best` | Matches the engine's top choice |
| `good` | Eval loss below the inaccuracy threshold |
| `inaccuracy` | Eval loss at or above `INACCURACY_CP` |
| `mistake` | Eval loss at or above `MISTAKE_CP` |
| `blunder` | Eval loss at or above `BLUNDER_CP` |
| `book` | Position still within the opening dataset |
| `forced` | Only legal move, or all alternatives lose materially |

Thresholds are configuration, never literals. Starting values are inherited from the
reference application and revisited at Phase 5 against real distributions.
