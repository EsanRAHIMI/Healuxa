from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from healuxa_py_common.errors import ApiError
from healuxa_py_common.middleware.auth import Principal
from identity_service.api.deps import get_current_principal, get_db, get_redis_client
from identity_service.domain.session_service import session_service
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])


def _require_permission(principal: Principal, permission: str) -> None:
    if permission not in principal.permissions:
        raise ApiError(status=403, code="forbidden", title="Forbidden", detail=f"Missing permission: {permission}")


@router.get("")
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query()] = None,
) -> dict:
    data, page_limit, next_cursor, has_more = await session_service.list_sessions(
        db,
        user_id=principal.user_id,
        limit=limit,
        cursor=cursor,
    )
    return {
        "data": [item.model_dump() for item in data],
        "page": {"next_cursor": next_cursor, "limit": page_limit, "has_more": has_more},
    }


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis_client),
    principal: Principal = Depends(get_current_principal),
) -> Response:
    _require_permission(principal, "sessions:revoke")
    await session_service.revoke_session(db, redis, user_id=principal.user_id, session_id=session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
