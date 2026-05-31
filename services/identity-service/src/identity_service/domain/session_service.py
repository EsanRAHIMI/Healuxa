from __future__ import annotations

from healuxa_py_common.errors import ApiError
from healuxa_py_common.events.envelope import EventActor
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from identity_service.config import settings
from identity_service.domain.schemas import SessionResponse
from identity_service.domain.security import utcnow
from identity_service.events.publisher import event_publisher
from identity_service.infra.models import Session
from identity_service.infra.session_cache import deny_session


class SessionService:
    async def list_sessions(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        limit: int = 20,
    ) -> tuple[list[SessionResponse], bool]:
        result = await db.execute(
            select(Session)
            .where(Session.user_id == user_id, Session.revoked_at.is_(None))
            .order_by(Session.created_at.desc())
            .limit(limit + 1)
        )
        rows = list(result.scalars())
        has_more = len(rows) > limit
        rows = rows[:limit]
        data = [
            SessionResponse(
                id=row.id,
                device=row.device,
                ip=row.ip,
                created_at=row.created_at.isoformat(),
                last_seen_at=row.last_seen_at.isoformat(),
            )
            for row in rows
        ]
        return data, has_more

    async def revoke_session(
        self,
        db: AsyncSession,
        redis,
        *,
        user_id: str,
        session_id: str,
    ) -> None:
        session = await db.get(Session, session_id)
        if not session or session.user_id != user_id:
            raise ApiError(status=404, code="not_found", title="Not found", detail="Session not found")
        if session.revoked_at is not None:
            return
        session.revoked_at = utcnow()
        await deny_session(redis, session_id, settings.jwt_refresh_ttl)
        await event_publisher.publish(
            event_type="auth.session_revoked",
            tenant_id=settings.tenant_default,
            payload={
                "user_id": user_id,
                "session_id": session_id,
                "scope": "single",
                "reason": "admin",
                "revoked_at": session.revoked_at.isoformat(),
            },
            actor=EventActor(type="user", id=user_id),
        )
        await db.commit()


session_service = SessionService()
