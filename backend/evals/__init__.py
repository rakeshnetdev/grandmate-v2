"""Evaluation harnesses, datasets, and score ledger (`evaluation-strategy.md`).

Deliberately outside `app/` — this is evaluation tooling, run on demand
(`uv run python -m evals.harness.retrieval_eval`), never imported by the application
itself. Always run from the `backend/` directory, same as every other `uv run` command
in this project.
"""
