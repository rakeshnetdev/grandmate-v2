"""One game measured against the player's own recent history (Phase 19, D-037).

Distinct from `domain/analytics`, which answers "how is this profile trending overall",
and from `domain/reports`, which answers "what happened in this game". This domain answers
the third question a player actually asks after finishing a game: *is this the same mistake
again, and am I getting better?*
"""

from app.domain.game_feedback.baseline import Baseline, load_baseline
from app.domain.game_feedback.comparison import GameComparison, compare_game_to_baseline
from app.domain.game_feedback.service import (
    REPORT_TYPE,
    PatternFeedback,
    PatternFeedbackService,
)

__all__ = [
    "REPORT_TYPE",
    "Baseline",
    "GameComparison",
    "PatternFeedback",
    "PatternFeedbackService",
    "compare_game_to_baseline",
    "load_baseline",
]
