"""One-shot `analysis`-bucket projection runner for a single game (Phase 7).

Manual trigger for `AnalysisProjectionService`, which is not yet wired into
`domain/analysis/dispatch.py`'s background job (a known, deliberate gap — see
`final_docs/v2/phase-reports/phase-07-knowledge-corpus-rag.md`). The game must already
have a completed engine analysis (`GameAnalysis`) — pattern/opening detection is
optional but richer if present, same as `AnalysisProjectionService.project_game` itself
requires. Needs a real `OPENAI_API_KEY` in `.env` and Postgres running.

Usage (from `backend/`):
    uv run python -m scripts.project_analysis <game_id>

Finding a game id: the API has no games-list route yet (a separately-tracked gap, see
prior phase reports), so either note the id `POST /api/v1/imports` implicitly created
via `GET /api/v1/imports`, or query the database directly:
    docker compose exec postgres psql -U grandmate -d grandmate \\
      -tA -c "SELECT id FROM games ORDER BY created_at DESC LIMIT 1;"
"""

from __future__ import annotations

import asyncio
import sys
import uuid

from app.core.config import get_settings
from app.db.session import create_engine, create_session_factory, session_scope
from app.domain.knowledge import AnalysisProjectionService
from app.integrations.llm import OpenAIEmbeddingProvider


async def main(game_id: uuid.UUID) -> None:
    settings = get_settings()
    embedding_provider = OpenAIEmbeddingProvider(settings.llm, settings.retrieval)
    engine = create_engine(settings.database)
    session_factory = create_session_factory(engine)

    try:
        async with session_scope(session_factory) as session:
            service = AnalysisProjectionService(session, embedding_provider)
            chunks = await service.project_game(game_id)
    finally:
        await engine.dispose()
        await embedding_provider.aclose()

    if not chunks:
        print(
            f"No chunks produced for game {game_id}. Either the game id is wrong, or "
            "it has no completed GameAnalysis yet (poll GET /api/v1/analysis/games/"
            "{game_id} until it returns 200 before running this)."
        )
        return

    by_kind: dict[str, int] = {}
    for chunk in chunks:
        by_kind[chunk.kind] = by_kind.get(chunk.kind, 0) + 1
    print(f"Projected {len(chunks)} chunk(s) for game {game_id}:")
    for kind, count in sorted(by_kind.items()):
        print(f"  {kind}: {count}")
    print("\nSample content:")
    for chunk in chunks[:5]:
        print(f"  [{chunk.kind}] {chunk.content}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: uv run python -m scripts.project_analysis <game_id>")
    try:
        parsed_game_id = uuid.UUID(sys.argv[1])
    except ValueError:
        sys.exit(f"{sys.argv[1]!r} is not a valid UUID")
    asyncio.run(main(parsed_game_id))
