"""Strategic theme detectors (Phase 6). See `registry.py` for the theme -> detector map
`PatternDetectionService` iterates, and `base.py` for the shared detector signature."""

from app.domain.patterns.themes.base import PlyContext, ThemeDetection, ThemeDetector
from app.domain.patterns.themes.registry import THEME_DETECTORS

__all__ = ["THEME_DETECTORS", "PlyContext", "ThemeDetection", "ThemeDetector"]
