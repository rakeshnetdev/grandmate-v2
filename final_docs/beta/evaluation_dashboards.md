# Evaluation Dashboards — GrandMate

This document details how metrics and telemetry are monitored using LangSmith, FastAPI structured logging, and direct SQL queries.

---

## 1. LangSmith Monitoring Dashboard

LangSmith is the central platform for observing agent performance in production. The dashboard focuses on three categories of metrics:

### 1. Accuracy & Grounding
* **Run Feedback**: Monitor thumbs-up/down events on chat responses (`feedbacks.thumb`).
* **Grounding Violations**: Track runs where the `critic` node rejected a coach's draft due to a grounding check failure (this indicates where the LLM is attempting to hallucinate).
* **Latency Trackers**: Alert on any coach -> critic -> coach iteration cycle that takes longer than **8 seconds** total.

### 2. Token & Cost Telemetry
* **Token Usage per Turn**: Monitor average and 99th-percentile token consumption across supervisor, retriever, and coach calls.
* **Cost Estimation**: Track daily and weekly OpenAI spend, ensuring it aligns with budget allocations.

### 3. Trajectory & Handoff Quality
* **Specialist Handoffs**: Trace supervisor routing decisions. Ensure that requests are routed to `retriever` and `chess_analyst` only when necessary, minimizing redundant LLM steps.

---

## 2. Server & Engine Metrics (FastAPI + Structlog)

Production monitoring logs are exported in JSON format, allowing easy ingestion into platforms like Grafana, Datadog, or Axiom.

### Key Structlog Fields to Alert On:
* `startup_analysis_sweep_failed`: Indicates the worker sweep failed to boot, leaving stuck jobs.
* `rate_limit_exceeded`: Tracks how often users hit the sliding-window rate limit (default 60/min), showing potential API abuse.
* `engine_analysis_failed`: Emitted when the Stockfish process crashes, hangs, or fails to return evaluations.
* `lichess_rate_limited` / `chesscom_rate_limited`: Alert if external platform connectors are hitting API rate limits.

---

## 3. SQL Operational Metrics (Database Dashboard)

For quick health checks, run these SQL queries directly against the Postgres database:

### 1. Job Queue & Completion Rate
Tracks the volume of imported games and how many are successfully analyzed by Stockfish:
```sql
SELECT 
  status, 
  COUNT(*), 
  AVG(EXTRACT(EPOCH FROM (completed_at - created_at))) as avg_duration_seconds
FROM jobs 
GROUP BY status;
```

### 2. Daily LLM Spend Guardrail
Ensure the daily token ceiling is functioning and monitor historical spend trends:
```sql
SELECT 
  day, 
  tokens_used, 
  updated_at 
FROM llm_usage_daily 
ORDER BY day DESC 
LIMIT 7;
```

### 3. User & Aggregation Activity
Monitor the active database footprint:
```sql
SELECT 
  (SELECT COUNT(*) FROM users) as total_users,
  (SELECT COUNT(*) FROM profiles) as total_profiles,
  (SELECT COUNT(*) FROM games) as total_games_analyzed;
```
