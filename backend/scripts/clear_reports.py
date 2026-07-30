"""Dev helper: delete cached persona reports so they regenerate through the current
prompt on next view (Phase 16b follow-up, added for prompt-iteration workflow).

Reports are a regenerable cache — `ReportService.get_or_generate`'s own docstring —
so deleting them is always safe: the next request for a game's report rebuilds it
from the stored analysis. Nothing else (games, analyses, patterns) is touched.

Usage (from `backend/`):
    uv run python -m scripts.clear_reports            # Analysis-tab reports only
    uv run python -m scripts.clear_reports --all      # also Story-tab reports
    uv run python -m scripts.clear_reports --story    # Story-tab reports only
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import delete

from app.core.config import get_settings
from app.db.models import GameReport
from app.db.session import create_engine, create_session_factory, session_scope


async def main(report_type: str | None) -> None:
    """`report_type` of None means every report type."""
    engine = create_engine(get_settings().database)
    session_factory = create_session_factory(engine)
    try:
        async with session_scope(session_factory) as session:
            statement = delete(GameReport)
            if report_type is not None:
                statement = statement.where(GameReport.report_type == report_type)
            result = await session.execute(statement)
        label = report_type or "all"
        print(f"deleted {result.rowcount} cached reports ({label})")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    flag = sys.argv[1] if len(sys.argv) > 1 else None
    if flag == "--all":
        selected = None
    elif flag == "--story":
        selected = "story"
    elif flag is None:
        selected = "findings"
    else:
        print(__doc__)
        raise SystemExit(2)
    asyncio.run(main(selected))
