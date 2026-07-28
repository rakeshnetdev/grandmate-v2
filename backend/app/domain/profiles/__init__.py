"""Multi-profile resolution: self vs. study, and cross-route ownership checks (Phase 8b,
D-021, ADR-0016)."""

from app.domain.profiles.queries import (
    get_linked_usernames,
    get_or_create_study_profile,
    get_owned_profile,
    list_profiles,
)

__all__ = [
    "get_linked_usernames",
    "get_or_create_study_profile",
    "get_owned_profile",
    "list_profiles",
]
