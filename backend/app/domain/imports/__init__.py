"""Ingestion: raw PGN parsing, validation, dedup, job tracking, and (Phase 14)
platform-sync dispatch."""

from app.domain.imports.connectors import ConnectorError, PlatformGameConnector
from app.domain.imports.dispatch import build_platform_connector, run_platform_import_job
from app.domain.imports.parsing import ParsedGame, ParseResult, RejectedGame, RejectionReason
from app.domain.imports.service import ImportResult, ImportService, SourceText, TooManyGamesError

__all__ = [
    "ConnectorError",
    "ImportResult",
    "ImportService",
    "ParseResult",
    "ParsedGame",
    "PlatformGameConnector",
    "RejectedGame",
    "RejectionReason",
    "SourceText",
    "TooManyGamesError",
    "build_platform_connector",
    "run_platform_import_job",
]
