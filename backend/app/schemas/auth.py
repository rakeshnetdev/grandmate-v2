"""Auth request and response schemas."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field, field_validator

from app.db.models import AuthProvider


class LoginRequest(BaseModel):
    """Log in by naming a platform account."""

    provider: AuthProvider
    username: str = Field(min_length=1, max_length=255)

    @field_validator("username")
    @classmethod
    def strip_username(cls, value: str) -> str:
        """Trim whitespace; a pasted username often carries some."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Username cannot be blank")
        return cleaned


class ProfileSummary(BaseModel):
    id: uuid.UUID
    display_name: str
    kind: str
    default_persona: str


class CurrentUser(BaseModel):
    """The signed-in user. Returned by login and by /auth/me."""

    id: uuid.UUID
    provider: AuthProvider
    username: str
    # False while login only proves the account exists, not that the caller owns it.
    verified: bool
    profile: ProfileSummary


__all__ = ["CurrentUser", "LoginRequest", "ProfileSummary"]
