from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from healuxa_py_common.middleware.auth import Principal
from identity_service.api.deps import get_current_principal, get_db, get_redis_client
from identity_service.domain.jwt_service import jwt_service

router = APIRouter(tags=["auth"])


@router.get("/.well-known/jwks.json")
async def get_jwks(db: AsyncSession = Depends(get_db)) -> dict:
    return await jwt_service.jwks(db)
