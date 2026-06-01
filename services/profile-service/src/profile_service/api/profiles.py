from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response
from healuxa_py_common.middleware.auth import Principal

from profile_service.api.deps import require_profile_permission
from profile_service.domain.profile_service import profile_service
from profile_service.domain.schemas import Profile

router = APIRouter(prefix="/v1/profiles", tags=["profiles"])


@router.get(
    "/{user_id}",
    response_model=Profile,
    operation_id="getProfile",
)
async def get_profile(
    user_id: str,
    response: Response,
    principal: Principal = Depends(require_profile_permission("profiles:read")),
) -> Profile:
    profile, etag = await profile_service.get_profile(user_id, principal=principal)
    response.headers["ETag"] = etag
    return profile


@router.put(
    "/{user_id}",
    response_model=Profile,
    operation_id="upsertProfile",
)
async def upsert_profile(
    user_id: str,
    body: Profile,
    response: Response,
    principal: Principal = Depends(require_profile_permission("profiles:write")),
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> Profile:
    profile, etag = await profile_service.upsert_profile(
        user_id,
        body,
        principal=principal,
        if_match=if_match,
    )
    response.headers["ETag"] = etag
    return profile
