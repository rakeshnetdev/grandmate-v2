"""Tactical motif detectors (Phase 6). See `registry.py` for the motif -> detector map
`PatternDetectionService` iterates, and `base.py` for the shared detector signature."""

from app.domain.patterns.motifs.base import MotifDetection, MotifDetector
from app.domain.patterns.motifs.registry import MOTIF_DETECTORS

__all__ = ["MOTIF_DETECTORS", "MotifDetection", "MotifDetector"]
