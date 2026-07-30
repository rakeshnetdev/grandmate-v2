# Persona Matrix

MVP personas: **self-learner**, **coach**, **kid**. Parent and analyst are deferred.

## The invariant

A persona changes how a finding is said. It never changes whether the finding is true.

Concretely: if the engine says 23...Nxe4 lost 280 centipawns to a knight fork on f2, then
all three personas must convey that the move was a serious error and that a fork was the
mechanism. What varies is whether the number appears, whether the motif is named
technically, how much surrounding context is given, and what the reader is told to do next.

This is enforced by the persona fidelity test suite, which renders the same analysis object
through every persona and asserts that the set of referenced fact ids is identical.

## Matrix

| Dimension | self-learner | coach | kid |
|-----------|-------------|-------|-----|
| **Audience** | The player, studying alone | A coach preparing a lesson | A junior player, roughly 8–14 |
| **Reading level** | Adult, chess-literate | Adult, chess-expert | Simple sentences, short paragraphs |
| **Centipawn values** | Hidden (game report — see addendum below); shown elsewhere (chat, training plan) | Shown, with PV lines | Hidden; described as "a big mistake" |
| **Motif naming** | Named and briefly explained | Named, assumed known | Named with a one-line plain explanation |
| **Depth per finding** | Medium | High, includes alternatives | Low, one idea at a time |
| **Findings per report** | Up to 2 positive + 3 mistake (game report — see addendum below); up to 5 elsewhere | Unbounded | At most 3 |
| **Tone** | Direct, neutral, third person (game report); direct, neutral, second person elsewhere | Concise, technical, peer-to-peer | Encouraging, never harsh |
| **Failure framing** | "White's Qh3 was a blunder — it cost the advantage" (game report); "This cost you the advantage" elsewhere | "Student drops material under time pressure in the Sicilian" | "Here's a chance to grab a free piece next time!" |
| **Recommendations** | Drills and study themes | Lesson plan structure and student-specific talking points | One concrete, achievable habit |
| **Engine lines** | Top line only | Multiple candidate lines | None |
| **Statistical caveats** | Shown when sample is thin | Always shown with sample sizes | Omitted, but thin-sample findings are suppressed entirely |

## Phase 16a addendum: self-learner's per-game report structure (D-035)

The self-learner persona's **per-game report only** (`domain/reports/service.py` →
`ReportService`, the Analysis tab's report — not chat, not the profile-level training
plan) follows a fixed structure on top of the tone rules above, requested directly by the
owner after reviewing the redesigned Analysis tab:

- Four sections, rendered by the frontend from tagged findings rather than
  model-authored markdown headers: Overview (the report's existing `summary`), What Went
  Well (up to `report_self_learner_positive_max` findings, `kind: "strength"`), Mistakes
  & Blunders (up to `report_self_learner_mistake_max` findings, `kind: "mistake"`,
  picked for how instructive they are rather than every notable move), Strategy to
  Improve (`recommendations`, each tied to a specific named mistake).
- Third person only — "White"/"Black"/a player's name, never "you"/"your". This is a
  narrower voice than the second-person framing this persona uses everywhere else (chat,
  training plans), scoped to this one report type.
- No engine numbers at all (previously this persona *did* show centipawn values,
  unlike kid) — a mistake finding names the better move in algebraic notation instead
  (`best_move_san`), and a strength finding names the tactical motif it landed
  (`motif`) rather than a numeric swing.
- A "What Went Well" finding requires a *landed tactic* at that ply (a motif finding on
  the mover's own side, e.g. a fork or pin — not the self-inflicted `HANGING_PIECE`),
  not merely "the engine's top choice" — most best moves in a game are unremarkable book
  moves and would make the section meaningless. (An earlier version tied this to
  `is_critical_moment` instead; verified against real analysis data that essentially
  never co-occurs with a `BEST` classification, since `is_critical_moment` is defined by
  a large centipawn *loss* and a best move has none by definition — corrected before
  shipping.)

Coach and kid are unaffected — the owner explicitly chose not to extend this structure
to coach (Phase 9's "unbounded, high depth" design for coach stands), and kid already had
its own no-blame, no-"blunder"-word framing that predates and is incompatible with this
format's literal classification-word requirement.

`domain/reports/critic.py`'s `validate_report` takes a `report_kind: "game" | "training"`
parameter so these self-learner-only rules apply to the per-game report and *not* to
Phase 15's training plan, which reuses the same persona and the same critic function but
predates and is untouched by this addendum.

## Role and persona are orthogonal

`profile_relationships.role` decides **whether** a user may see a profile.
The persona setting decides **how** it reads. They are independently selectable.

Valid and expected combinations:

| Role | Persona | Scenario |
|------|---------|----------|
| owner | self-learner | Player reviewing their own games |
| owner | kid | Junior player reviewing their own games |
| coach | coach | Coach preparing a lesson |
| coach | kid | Coach drafting language to use with a young student |
| parent | coach | Parent who wants real detail, not simplified output |

The last row is the reason these must not be merged. Assuming a parent wants the kid
persona would be both patronising and wrong.

## Safety rules for the kid persona

- No harsh or demeaning framing of mistakes, ever.
- No unbounded free text from the model without the grounding guardrail applied.
- Suppress rather than soften findings with low confidence or thin sample support. A young
  player acting on a false pattern is a real harm, not a cosmetic one.
- Content safety tests run against generated kid-persona output in Phase 9.

## Deferred personas

Documented now so the layer is designed to accommodate them without rework.

| Persona | Intended audience | Distinguishing need |
|---------|------------------|---------------------|
| parent | Parent of a junior | Progress over time, effort signals, no chess expertise assumed |
| analyst | Tournament preparation | Opponent tendencies, repertoire gaps, explicitly permission-sensitive |

The analyst persona carries a privacy dimension the others do not: it renders findings
about someone who has not consented to being analysed. It stays deferred until the
permission model in ADR-0012 has been exercised in practice.

## Implementation constraint

The persona layer is a transformation over an already-computed analysis object. It sits in
`domain/reports` and `domain/chat`, downstream of everything deterministic. It receives
facts and emits phrasing. If persona code ever needs to call the engine, the layering has
been violated.
