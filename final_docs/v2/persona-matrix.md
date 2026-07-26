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
| **Centipawn values** | Shown | Shown, with PV lines | Hidden; described as "a big mistake" |
| **Motif naming** | Named and briefly explained | Named, assumed known | Named with a one-line plain explanation |
| **Depth per finding** | Medium | High, includes alternatives | Low, one idea at a time |
| **Findings per report** | Up to 5 | Unbounded | At most 3 |
| **Tone** | Direct, neutral | Concise, technical, peer-to-peer | Encouraging, never harsh |
| **Failure framing** | "This cost you the advantage" | "Student drops material under time pressure in the Sicilian" | "Here's a chance to grab a free piece next time!" |
| **Recommendations** | Drills and study themes | Lesson plan structure and student-specific talking points | One concrete, achievable habit |
| **Engine lines** | Top line only | Multiple candidate lines | None |
| **Statistical caveats** | Shown when sample is thin | Always shown with sample sizes | Omitted, but thin-sample findings are suppressed entirely |

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
