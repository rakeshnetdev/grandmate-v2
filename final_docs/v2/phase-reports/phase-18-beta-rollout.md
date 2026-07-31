# Phase 18 Report — Beta Rollout and Evaluation Loop

**Date**: 2026-07-31  
**Status**: Complete, pending sign-off  
**Branch**: `P18-beta-rollout`  

## Goal

Validate GrandMate's value proposition with real users, outline target cohort structures, construct quantitative and qualitative feedback rubrics, establish observability dashboards, define pre-release production checks, and build a prioritised post-beta product backlog.

---

## Design and Implementation

We have designed and checked in the complete operational and validation framework for the Phase 18 Beta:

### 1. Cohort Plan
* **Demographics**: Structured a cohort of 35–50 active testers mapping to three core target personas: Self-Directed Club Players (`self_learner`), Chess Coaches (`coach`), and Junior Players (`kid`).
* **Timeline**: Established a 4-week gantt-tracked rollout starting with an internal developer dry-run, expanding to club players, and finalising with coach-led groups.
* **Onboarding**: Defined profile link rules and step-by-step game loading onboarding workflows.
* **Link**: [cohort_plan.md](file:///Users/sriraki/Desktop/CodePractice/ai_practice/AE-CH/demo-prj/grandmate-v2/docs/beta/cohort_plan.md)

### 2. Feedback Rubric
* **Quantitative**: Incorporated targets for System Usability Scale (SUS > 78), Net Promoter Score (NPS > +35), and in-app telemetry ratings.
* **Qualitative Taxonomy**: Defined explicit category codes for categorising and tagging user feedback (e.g. `ERR_CHESS_HALLUCINATION`, `ERR_PERSONA_VOICE`, `ERR_INGESTION_FAIL`).
* **SLA Severity Guidelines**: Established support SLAs ranging from 4-hour critical hotfixes (Severity 1) to 72-hour minor enhancements (Severity 3).
* **Link**: [feedback_rubric.md](file:///Users/sriraki/Desktop/CodePractice/ai_practice/AE-CH/demo-prj/grandmate-v2/docs/beta/feedback_rubric.md)

### 3. Evaluation Dashboards
* **LangSmith Monitoring**: Outlined metrics for tracking chat accuracy, grounding violations, tokens used, and latency.
* **Structured Logs**: Documented critical logging events (e.g., rate limits, worker crashes) to monitor with structlog.
* **Direct SQL Queries**: Provided queries to track active users, Stockfish analysis completion rates, and daily LLM token spend.
* **Link**: [evaluation_dashboards.md](file:///Users/sriraki/Desktop/CodePractice/ai_practice/AE-CH/demo-prj/grandmate-v2/docs/beta/evaluation_dashboards.md)

### 4. Release Checklist
* **Pre-Flight Checks**: Formalised verification steps for secrets provisioning, Docker volume/RAM constraints, vector migrations (pgvector), and dataset/corpus index availability.
* **End-to-End Walkthrough**: Step-by-step manual checks to run from imports to persona switching and agent chat grounding.
* **Link**: [release_checklist.md](file:///Users/sriraki/Desktop/CodePractice/ai_practice/AE-CH/demo-prj/grandmate-v2/docs/beta/release_checklist.md)

### 5. Prioritised Post-Beta Backlog
* **High Priority**: Deferred items like promoting multi-agent graph to default chat, adding live OAuth for chess platforms (Lichess/Chess.com), and multi-session cache warming.
* **Medium Priority**: PDF report export and configurable Stockfish engine depth settings.
* **Low Priority**: Social sharing/achievements and browser-side WebAssembly Stockfish.
* **Link**: [post_beta_backlog.md](file:///Users/sriraki/Desktop/CodePractice/ai_practice/AE-CH/demo-prj/grandmate-v2/docs/beta/post_beta_backlog.md)

---

## Files Created or Changed

```
docs/beta/
├── cohort_plan.md          # Phased rollout and demographic mapping
├── feedback_rubric.md      # Usability metrics and tagging taxonomy
├── evaluation_dashboards.md# Telemetry and sql operations tracking
├── release_checklist.md    # Production deployment verification
└── post_beta_backlog.md    # Post-beta feature prioritization
```

---

## Verification and Evaluation

* All markdown files have been checked for formatting, relative links, and Mermaid syntax compatibility.
* Verified that project structure and file naming align with Phase 18 goals and metrics listed in `project-plan.md`.
