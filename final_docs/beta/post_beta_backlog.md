# Post-Beta Prioritised Backlog — GrandMate

This backlog collects and prioritizes enhancements, optimizations, and deferred features for implementation after the beta testing phase resolves.

---

## 1. High Priority (Immediate Post-Beta)

### B-001: Promote Multi-Agent Graph to Default Chat Path
* **Trigger**: Multi-agent evaluation passes validation criteria (evaluation score beats the single-agent baseline on correctness and persona accuracy).
* **Work**:
  * Swap `USE_MULTI_AGENT` default value to `true` in `settings.py`.
  * Archive the legacy single-agent graph `graphs/chat.py` to prevent duplicate maintenance paths.

### B-002: Live OAuth for Chess Platforms
* **Problem**: Currently, we query public profile endpoints using usernames without explicit authorization.
* **Work**:
  * Implement Lichess OAuth2 code flow with PKCE.
  * Store refresh tokens in user sessions to support silent background game syncs.

### B-003: Multi-Session Cache Warmup
* **Problem**: First-time game list imports trigger high-latency Stockfish workers.
* **Work**:
  * Implement an asynchronous cache-warming task that triggers when users link their accounts.
  * Pre-analyze the user's last 5 games silently before their first dashboard visit.

---

## 2. Medium Priority (Next Release Cycle)

### B-004: PDF Report Export
* **Problem**: Coaches want printable training plans and game summaries to share with students.
* **Work**:
  * Implement a canvas-based report builder.
  * Render weaknesses, opening stats, and customized coaching advice into a clean, downloadable PDF.

### B-005: Custom Stockfish Depth Settings
* **Problem**: Advanced club players want deeper engine scans (e.g. depth 16/20) for tactical accuracy, while casual players are fine with faster depth 12.
* **Work**:
  * Expose an engine depth slider in user settings.
  * Dynamically scale worker job timeout limits based on requested depth.

---

## 3. Low Priority (Backlog)

### B-006: Social Sharing & Badges
* **Work**: Allow users to share training milestones (e.g., "Blunder-free streak: 5 games") to social channels (X, Discord).
* **Status**: Deferred indefinitely, pending user engagement metrics.

### B-007: Local Stockfish Engine Support (WASm)
* **Work**: Offload engine analysis to the browser via WebAssembly to reduce server CPU costs.
* **Status**: Under research; depends on browser support for multi-threading.
