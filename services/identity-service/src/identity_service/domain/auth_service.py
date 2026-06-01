from __future__ import annotations

from datetime import timedelta

from healuxa_py_common.errors import ApiError
from healuxa_py_common.events.envelope import EventActor
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from ulid import ULID

from identity_service.config import settings
from identity_service.domain.jwt_service import jwt_service
from identity_service.domain.schemas import (
    IntrospectionResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
)
from identity_service.domain.security import (
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    utcnow,
    verify_client_secret,
    verify_password,
)
from identity_service.domain.idempotency import (
    hash_request_body,
    read_idempotent_response,
    store_idempotent_response,
)
from identity_service.events.publisher import event_publisher
from identity_service.infra.models import (
    Credential,
    JwksKey,
    LoginHistory,
    Role,
    ServiceClient,
    Session,
    User,
    UserRole,
)
from identity_service.infra.session_cache import deny_session, is_locked_out, is_session_denied, set_lockout


async def _resolve_permissions(db: AsyncSession, user: User) -> tuple[list[str], list[str]]:
    result = await db.execute(
        select(Role).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user.id)
    )
    roles = result.scalars().all()
    role_names = [role.name for role in roles]
    permissions: set[str] = set()
    for role in roles:
        permissions.update(role.permissions or [])
    return role_names, sorted(permissions)


async def _issue_tokens(db: AsyncSession, *, user: User, session: Session) -> TokenResponse:
    await jwt_service.ensure_active_key(db)
    role_names, permissions = await _resolve_permissions(db, user)
    access_token, expires_in = jwt_service.issue_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        roles=role_names,
        permissions=permissions,
        session_id=session.id,
    )
    refresh_token = new_refresh_token()
    session.refresh_token_hash = hash_refresh_token(refresh_token)
    session.last_seen_at = utcnow()
    await db.commit()
    return TokenResponse(
        access_token=access_token,
        token_type="Bearer",
        expires_in=expires_in,
        refresh_token=refresh_token,
    )


async def _record_login(
    db: AsyncSession,
    *,
    identifier: str,
    user_id: str | None,
    success: bool,
    ip: str | None,
    reason: str | None = None,
) -> None:
    db.add(
        LoginHistory(
            id=str(ULID()),
            user_id=user_id,
            identifier=identifier,
            success=success,
            ip=ip,
            reason=reason,
        )
    )


class AuthService:
    async def register(
        self,
        db: AsyncSession,
        redis,
        body: RegisterRequest,
        *,
        ip: str | None,
        idempotency_key: str | None,
    ) -> tuple[TokenResponse, str]:
        body_hash = hash_request_body(body.model_dump())
        if idempotency_key:
            cached = await read_idempotent_response(db, idempotency_key, request_hash=body_hash)
            if cached:
                body_data = dict(cached)
                location = body_data.pop("_location", f"/v1/sessions/unknown")
                return TokenResponse(**body_data), location

        tenant_id = settings.tenant_default
        identifier = body.identifier.strip().lower()
        existing = await db.scalar(
            select(User.id).where(User.tenant_id == tenant_id, User.identifier == identifier)
        )
        if existing:
            raise ApiError(
                status=409,
                code="conflict",
                title="Conflict",
                detail="Identifier already registered",
            )

        default_role = await db.scalar(
            select(Role).where(Role.tenant_id == tenant_id, Role.name == "user")
        )

        user_id = str(ULID())
        user = User(
            id=user_id,
            tenant_id=tenant_id,
            identifier=identifier,
            locale=body.locale,
        )
        credential = Credential(
            id=str(ULID()),
            user_id=user_id,
            password_hash=hash_password(body.password),
        )
        session = Session(
            id=str(ULID()),
            user_id=user_id,
            refresh_token_hash="pending",
            device="unknown",
            ip=ip,
        )
        db.add(user)
        db.add(credential)
        db.add(session)
        if default_role:
            db.add(UserRole(user_id=user_id, role_id=default_role.id))

        try:
            await db.flush()
        except IntegrityError as exc:
            await db.rollback()
            raise ApiError(
                status=409,
                code="conflict",
                title="Conflict",
                detail="Identifier already registered",
            ) from exc

        tokens = await _issue_tokens(db, user=user, session=session)
        await event_publisher.publish(
            event_type="auth.user_registered",
            tenant_id=tenant_id,
            payload={
                "user_id": user_id,
                "channel": "web",
                "registered_at": utcnow().isoformat(),
            },
            actor=EventActor(type="user", id=user_id),
        )

        location = f"/v1/sessions/{session.id}"
        if idempotency_key:
            stored = dict(tokens.model_dump())
            stored["_location"] = location
            await store_idempotent_response(
                db,
                idempotency_key,
                request_hash=body_hash,
                status_code=201,
                response_body=stored,
            )
        return tokens, location

    async def login(
        self,
        db: AsyncSession,
        redis,
        body: LoginRequest,
        *,
        ip: str | None,
    ) -> TokenResponse:
        if body.mfa_code:
            raise ApiError(
                status=422,
                code="unprocessable",
                title="Unprocessable",
                detail="MFA is not enabled on this deployment",
            )
        identifier = body.identifier.strip().lower()
        if await is_locked_out(redis, identifier):
            raise ApiError(
                status=429,
                code="rate_limited",
                title="Too many requests",
                detail="Account temporarily locked",
            )

        user = await db.scalar(
            select(User)
            .options(selectinload(User.credential))
            .where(User.identifier == identifier, User.tenant_id == settings.tenant_default)
        )
        if not user or not user.credential:
            await _record_login(db, identifier=identifier, user_id=None, success=False, ip=ip, reason="invalid_credentials")
            await db.commit()
            raise ApiError(status=401, code="unauthorized", title="Unauthorized", detail="Invalid credentials")

        if user.locked_until and user.locked_until > utcnow():
            raise ApiError(status=429, code="rate_limited", title="Too many requests", detail="Account locked")

        if not verify_password(body.password, user.credential.password_hash):
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= settings.login_max_attempts:
                user.locked_until = utcnow() + timedelta(seconds=settings.lockout_seconds)
                await set_lockout(redis, identifier, settings.lockout_seconds)
                await event_publisher.publish(
                    event_type="auth.security_event",
                    tenant_id=user.tenant_id,
                    payload={
                        "user_id": user.id,
                        "kind": "lockout",
                        "severity": "warning",
                        "ip": ip,
                        "detected_at": utcnow().isoformat(),
                    },
                )
            await _record_login(
                db,
                identifier=identifier,
                user_id=user.id,
                success=False,
                ip=ip,
                reason="invalid_credentials",
            )
            await db.commit()
            raise ApiError(status=401, code="unauthorized", title="Unauthorized", detail="Invalid credentials")

        user.failed_login_attempts = 0
        user.locked_until = None
        session = Session(
            id=str(ULID()),
            user_id=user.id,
            refresh_token_hash="pending",
            device="unknown",
            ip=ip,
        )
        db.add(session)
        await _record_login(db, identifier=identifier, user_id=user.id, success=True, ip=ip)
        await db.flush()
        return await _issue_tokens(db, user=user, session=session)

    async def refresh(self, db: AsyncSession, redis, refresh_token: str) -> TokenResponse:
        token_hash = hash_refresh_token(refresh_token)
        session = await db.scalar(
            select(Session).where(Session.refresh_token_hash == token_hash, Session.revoked_at.is_(None))
        )
        if not session:
            previous = await db.scalar(select(Session).where(Session.previous_refresh_token_hash == token_hash))
            if previous:
                await self._revoke_all_user_sessions(db, redis, previous.user_id, reason="token_reuse")
                await event_publisher.publish(
                    event_type="auth.security_event",
                    tenant_id=settings.tenant_default,
                    payload={
                        "user_id": previous.user_id,
                        "kind": "token_reuse",
                        "severity": "critical",
                        "detected_at": utcnow().isoformat(),
                    },
                )
            raise ApiError(status=401, code="unauthorized", title="Unauthorized", detail="Invalid refresh token")

        user = await db.get(User, session.user_id)
        if not user:
            raise ApiError(status=401, code="unauthorized", title="Unauthorized", detail="Invalid refresh token")

        session.previous_refresh_token_hash = session.refresh_token_hash
        return await _issue_tokens(db, user=user, session=session)

    async def logout(self, db: AsyncSession, redis, *, access_token: str) -> None:
        claims = await self._claims_from_token(db, access_token)
        if not claims:
            raise ApiError(status=401, code="unauthorized", title="Unauthorized", detail="Invalid token")
        session_id = claims.get("session_id")
        user_id = claims.get("sub")
        if not session_id or not user_id:
            raise ApiError(status=401, code="unauthorized", title="Unauthorized", detail="Invalid token")
        session = await db.get(Session, session_id)
        if session and session.revoked_at is None:
            session.revoked_at = utcnow()
            await deny_session(redis, session_id, settings.jwt_refresh_ttl)
            await event_publisher.publish(
                event_type="auth.session_revoked",
                tenant_id=claims.get("tenant", settings.tenant_default),
                payload={
                    "user_id": user_id,
                    "session_id": session_id,
                    "scope": "single",
                    "reason": "logout",
                    "revoked_at": utcnow().isoformat(),
                },
                actor=EventActor(type="user", id=user_id),
            )
            await db.commit()

    async def introspect(self, db: AsyncSession, redis, token: str) -> IntrospectionResponse:
        claims = await self._claims_from_token(db, token)
        if not claims:
            return IntrospectionResponse(active=False)
        session_id = claims.get("session_id")
        if session_id and await is_session_denied(redis, session_id):
            return IntrospectionResponse(active=False)
        if session_id:
            session = await db.get(Session, session_id)
            if not session or session.revoked_at is not None:
                return IntrospectionResponse(active=False)
        return IntrospectionResponse(
            active=True,
            sub=claims.get("sub"),
            tenant=claims.get("tenant"),
            roles=claims.get("roles", []),
            perms=claims.get("perms", []),
            session_id=session_id,
        )

    async def issue_service_token(self, db: AsyncSession, client_id: str, client_secret: str) -> TokenResponse:
        client = await db.get(ServiceClient, client_id)
        if client and verify_client_secret(client_secret, client.client_secret_hash):
            pass
        elif client_id == settings.service_auth_client_id and client_secret == settings.service_auth_client_secret:
            pass
        else:
            raise ApiError(status=401, code="unauthorized", title="Unauthorized", detail="Invalid service credentials")

        await jwt_service.ensure_active_key(db)
        access_token, expires_in = jwt_service.issue_access_token(
            user_id=client_id,
            tenant_id=settings.tenant_default,
            roles=["service"],
            permissions=["service"],
            session_id=f"svc-{client_id}",
            ttl_seconds=settings.jwt_access_ttl,
            subject_type="service",
        )
        return TokenResponse(access_token=access_token, token_type="Bearer", expires_in=expires_in)

    async def _claims_from_token(self, db: AsyncSession, token: str) -> dict | None:
        result = await db.execute(select(JwksKey))
        keys = list(result.scalars())
        return jwt_service.decode_access_token(token, keys)

    async def _revoke_all_user_sessions(self, db: AsyncSession, redis, user_id: str, *, reason: str) -> None:
        result = await db.execute(
            select(Session).where(Session.user_id == user_id, Session.revoked_at.is_(None))
        )
        now = utcnow()
        for session in result.scalars():
            session.revoked_at = now
            await deny_session(redis, session.id, settings.jwt_refresh_ttl)
        await event_publisher.publish(
            event_type="auth.session_revoked",
            tenant_id=settings.tenant_default,
            payload={
                "user_id": user_id,
                "scope": "all",
                "reason": reason,
                "revoked_at": now.isoformat(),
            },
        )
        await db.commit()

auth_service = AuthService()
