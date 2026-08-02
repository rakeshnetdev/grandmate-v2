# Phase 20 Report — Knowledge Citations

**Date**: 2026-08-02
**Status**: Complete, pending sign-off
**Branch**: `P20-knowledge-citations`

## Goal

Make a general chess question answerable on the first attempt while an unrelated game is
open. It was not, and the failure was structural rather than a prompt-tuning problem.

## The bug

Asking "explain the French Defence" with a Caro-Kann game open produced the deterministic
fallback. Traced through the checkpoint history by the owner:

1. The agent called `search_knowledge` and got the right material back.
2. The system prompt requires a citation for every chess fact stated, and an explanation
   of the French Defence states plenty.
3. All four citation kinds required either a `game_id` (`move`, `evaluation`, `opening`) or
   a FEN (`variation`). There was no kind for a fact learned from the corpus.
4. So the model attached the only id in scope — the open game's — claiming that game's
   opening was the French Defence. It was a Caro-Kann. The guardrail correctly rejected it.
5. Two attempts, then fallback. The user got nothing, from an answer that was actually
   right.

The model was not hallucinating. It was satisfying a schema that had no correct option.

## What was ruled out

The cheaper fix — telling the prompt to leave `citations` empty for retrieved facts — was
rejected. It instructs the model to ship real chess claims uncited, which is exactly the
hole the guardrail exists to close. It trades a visible failure for a silent one.

Also corrected in passing: an earlier analysis (from another assistant) claimed the
multi-agent path already avoided this via `needs_analysis` routing. It does not.
`multi_agent_prompts.py` had the same missing kind, stated the open game unconditionally,
and carried the same "every factual chess claim must have a matching citation object" rule
— and `USE_MULTI_AGENT=false` means it is not the shipped path anyway. Both paths are fixed
here.

## Design

**A `knowledge` citation, verified against what was actually retrieved.** The owner chose
the stricter of the two options offered: the cited chunk must be one a retrieval tool
returned *during this turn*, not merely one that exists in the corpus. The weaker check
would have let the model cite any real document for any assertion.

- `knowledge_tools.py` — `_chunk_payload` now exposes `chunk_id`. `RetrievedChunk` already
  carried it; the payload was dropping it, which is why there was nothing citable.
- `guardrail.retrieved_chunk_ids()` — reads the ids off the recorded tool *results*, which
  are server-side truth about what the tool returned rather than the model's account of it.
  Both graphs record results in the same shape, so this is one implementation shared by the
  single-agent loop (`turn_context`) and the multi-agent critic (`_combined_context`), per
  rule 13.
- `guardrail._check_knowledge` — membership check, then fills `title`/`source` from the
  document record. **The model supplies only the id**; every human-readable field is
  database truth. That is stricter than the other kinds, which accept a model-written SAN
  or ECO and then verify it — here the model never gets to write the label at all.
- The title lookup is best-effort by design: `search_analysis` returns chunks from
  `analysis_knowledge_chunks`, which has no parent document. A verified analysis chunk
  simply carries no title, and the UI labels it "Knowledge corpus". Absence of a title is
  not a grounding failure — membership in the retrieved set is what makes the citation true.

**The prompt's framing of the open game.** `prompts.py` previously said "Prefer tools
scoped to that game", which combined with the missing kind to point the model at the open
game for everything. It now states the open game as available context and says plainly that
a general question is not about it and must not be answered with facts or citations drawn
from it. Same correction in `multi_agent_prompts.py`.

## Files

**Backend**: `orchestration/tools/knowledge_tools.py`, `domain/chat/guardrail.py`,
`domain/chat/prompts.py`, `domain/chat/multi_agent_prompts.py`,
`orchestration/graphs/chat.py`, `orchestration/graphs/multi_agent.py`
**Frontend**: `features/chat/components/CitationList.tsx` (the `ChatCitation` schema is
`passthrough()`, so no schema change was needed — the opposite of Phase 19's zod trap)
**Docs**: `decisions-log.md` (D-038), this report

## Tests

| Suite | Count | Covers |
|-------|-------|--------|
| `test_chat_guardrail.py` | +6 | A chunk retrieved this turn validates and gains its title; a real chunk *not* retrieved this turn is rejected; a citation without `chunk_id` is rejected; `retrieved_chunk_ids` collects across both retrieval tools and ignores errors/non-retrieval results |
| `test_chat_graph.py` | +2 | The reported failure end to end — a general question answered on the first attempt with an unrelated game open — and a fabricated chunk id still falling back |
| `CitationList.test.tsx` | +2 | Document-backed and document-less knowledge citations render distinctly |

**Results**: backend `ruff check .`, `ruff format --check .`, `mypy app`, and 174 tests
across the chat, retrieval, tools, and multi-agent suites pass. Frontend `lint`,
`format:check`, `tsc --noEmit`, `build`, and all 158 tests pass. (Phase 19 shipped with a
CI failure because I checked `oxlint` and `tsc` but not `prettier`; this phase was run
against the full CI list from both workflow files.)

## Live verification

Reproduced the original scenario against the running app — a chat thread with the same
Caro-Kann game open, asking "explain the French Defence opening":

```
grounded: True
answer:   "The French Defence is initiated with the moves 1.e4 e6. This opening aims to
           build a solid pawn chain, allowing Black to later play ...d5. …"
citations: [{"kind": "knowledge",
             "chunk_id": "0fb07d6c-…",
             "title": "Opening Families Reference",
             "source": "GrandMate original prose (Phase 7); ECO data from
                        lichess-org/chess-openings (CC0)"}]
```

First attempt, grounded, citing real corpus material with a server-filled title. No
game-scoped citation, no retry, no fallback.

## Known gaps

1. **No RAGAS run.** The retrieval harness scores retrieval quality; what changed here is
   the citation contract, which the deterministic guardrail covers. If the owner wants
   answer-quality scored against this change, that is its own increment.
2. **`title` enrichment costs one query per knowledge citation.** Fine at current volume.
   The alternative — joining the document in the retrieval layer so `_chunk_payload`
   carries the title — would remove the query but changes Phase 7 code for a display
   concern, so it was not taken.
3. **The multi-agent path is fixed but unshipped** (`USE_MULTI_AGENT=false`), so it is
   covered by unit tests rather than live verification.

## Recommendation

Ready for sign-off. The failing case now passes on the first attempt in the real app, and
the new citation kind is verified more strictly than any existing one.
