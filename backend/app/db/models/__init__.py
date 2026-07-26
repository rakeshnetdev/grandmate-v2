"""ORM models.

Every model must be imported here. Alembic's autogenerate compares ``Base.metadata``
against the live database, and a model that is never imported is absent from that
metadata — so autogenerate would silently emit a migration dropping its table.
"""

from app.db.models.audit import AuditAction, AuditEvent
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
from app.db.models.imports import Game, GameColor, Job, JobKind, JobStatus

__all__ = [
    "AuditAction",
    "AuditEvent",
    "AuthProvider",
    "Game",
    "GameColor",
    "GameSource",
    "Job",
    "JobKind",
    "JobStatus",
    "Persona",
    "Profile",
    "ProfileKind",
    "ProfileRelationship",
    "ProfileSource",
    "RelationshipRole",
    "User",
    "UserIdentity",
]
