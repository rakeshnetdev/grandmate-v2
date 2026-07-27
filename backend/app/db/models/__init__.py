"""ORM models.

Every model must be imported here. Alembic's autogenerate compares ``Base.metadata``
against the live database, and a model that is never imported is absent from that
metadata — so autogenerate would silently emit a migration dropping its table.
"""

from app.db.models.analysis import GameAnalysis, MoveClassification, MoveEvaluation
from app.db.models.audit import AuditAction, AuditEvent
from app.db.models.games import Game, GameColor, GameMove
from app.db.models.identity import (
    AuthProvider,
    GameSource,
    Persona,
    Profile,
    ProfileKind,
    ProfileRelationship,
    ProfileSource,
    RelationshipRole,
    User,
    UserIdentity,
)
from app.db.models.imports import Job, JobKind, JobStatus

__all__ = [
    "AuditAction",
    "AuditEvent",
    "AuthProvider",
    "Game",
    "GameAnalysis",
    "GameColor",
    "GameMove",
    "GameSource",
    "Job",
    "JobKind",
    "JobStatus",
    "MoveClassification",
    "MoveEvaluation",
    "Persona",
    "Profile",
    "ProfileKind",
    "ProfileRelationship",
    "ProfileSource",
    "RelationshipRole",
    "User",
    "UserIdentity",
]
