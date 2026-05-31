from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class RegisterRequest(BaseModel):
    identifier: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8)
    locale: str | None = None

    @field_validator("locale")
    @classmethod
    def validate_locale(cls, value: str | None) -> str | None:
        if value is None:
            return value
        allowed = {"en", "ar", "fa", "ru"}
        if value not in allowed:
            raise ValueError("locale must be one of en, ar, fa, ru")
        return value


class LoginRequest(BaseModel):
    identifier: str
    password: str
    mfa_code: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class IntrospectRequest(BaseModel):
    token: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    refresh_token: str | None = None


class IntrospectionResponse(BaseModel):
    active: bool
    sub: str | None = None
    tenant: str | None = None
    roles: list[str] | None = None
    perms: list[str] | None = None
    session_id: str | None = None


class SessionResponse(BaseModel):
    id: str
    device: str | None = None
    ip: str | None = None
    created_at: str
    last_seen_at: str


class RoleRequest(BaseModel):
    name: str
    permissions: list[str]
    tenant_id: str | None = None


class RoleResponse(BaseModel):
    name: str
    permissions: list[str]
    tenant_id: str | None = None
