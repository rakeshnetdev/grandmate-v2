# Feedback Rubric — GrandMate

This document details the quantitative and qualitative rubrics used to collect, tag, and triage user feedback during the GrandMate beta phase.

---

## 1. Quantitative Usability Rubrics

We will collect quantitative product feedback through two main instruments: in-app telemetry and a post-trial survey.

### In-App Telemetry (Micro-Feedback)
Every chat turn and report generation includes a thumbs-up/thumbs-down component.
* **Chat Usefulness**: Ratio of positive votes to total responses. Target: **> 85%**.
* **Memory Accuracy**: Thumbs-down with tag `incorrect_memory` triggers review of the stored memory block. Target: **< 5%** memory deletion rate.
* **Report Clarity**: Rating (1-5 stars) on generated game reviews. Target average: **> 4.2/5**.

### Post-Trial Survey (Macro-Feedback)
After 2 weeks of usage, beta testers complete a feedback form mapping to:
* **System Usability Scale (SUS)**: Standard 10-question rubric evaluating complexity and ease of use. Target score: **> 78 (Grade A-)**.
* **Net Promoter Score (NPS)**: "How likely are you to recommend GrandMate to a friend or student?" (Scale 0-10). Target: **> +35**.
* **Persona Satisfaction**: Ratings segregated by user role:
  * Self-learners: Accuracy of weakness identification.
  * Coaches: Speed and utility of lessons preparation.
  * Kids: Comprehensibility of terms and safety.

---

## 2. Qualitative Feedback Taxonomy

All written user feedback (from free-text input and support channels) is cataloged and tagged using the following taxonomy:

| Category Code | Label | Description | Example User Quote |
|---|---|---|---|
| **ERR_CHESS_HALLUCINATION** | Hallucinated Chess | LLM chat or report refers to a move, FEN position, or opening variation that was never played. | *"The assistant says I played d4 on move 12, but we were in a French Defense and I never moved my d-pawn."* |
| **ERR_CHESS_RULES** | Legal Rule Violation | LLM states something that violates chess rules (e.g., claiming a checkmate when there is an escape square). | *"The coach report said my king was trapped, but I could just block the check with my bishop."* |
| **ERR_MOTIF_MISTAG** | Motif Classification Error | Stockfish core tagged a motif (e.g., Fork, Skewer, Pin) incorrectly or missed one. | *"The analysis page tagged my move as a skewer, but it was just a simple defensive trade."* |
| **ERR_PERSONA_VOICE** | Persona Violations | The tone is mismatched (e.g., Kid persona uses complex centipawn values, or self-learner report uses third-person). | *"My kid's dashboard tells him he lost 300 centipawns. He doesn't know what that means."* |
| **ERR_PERF_LATENCY** | Performance / Slowness | The interface takes too long to load or Stockfish analysis takes minutes to complete. | *"I pasted my game and it was stuck on 'analyzing' for three minutes before I could see anything."* |
| **ERR_INGESTION_FAIL** | Import / Parsing Failure | A PGN fails to import, or sync with Lichess fails. | *"My Chess.com import completed with 0 games even though I played five yesterday."* |

---

## 3. Triage & SLA Severity Guidelines

Issues identified during beta are triaged by the development team within the following SLA windows:

### Severity 1 (Critical) — SLA: 4 Hours
* **Scope**: Total platform outage, security/privacy data leakage between profiles, or persistent engine worker crash loops.
* **Action**: Immediate hotfix deploy on `main`.

### Severity 2 (Major) — SLA: 24 Hours
* **Scope**: LLM hallucination in chess variations, rate limiting blocking legitimate users, or PGN import failures.
* **Action**: Branch fix pushed to staging, tested against the evaluation suite, and merged.

### Severity 3 (Minor) — SLA: 72 Hours
* **Scope**: Typos in persona phrasing, UI alignment issues on mobile viewports, or minor latency delays in non-blocking routes.
* **Action**: Scheduled patch release.
