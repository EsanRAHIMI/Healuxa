from __future__ import annotations

from typing import Any

from healuxa_py_common.errors import ApiError
from healuxa_py_common.events.envelope import EventActor
from healuxa_py_common.middleware.auth import Principal
from motor.motor_asyncio import AsyncIOMotorCollection
from pymongo import ReturnDocument

from profile_service.config import settings
from profile_service.domain.schemas import Profile
from profile_service.domain.security import format_etag, utcnow
from profile_service.events.publisher import event_publisher
from profile_service.infra.mongo import get_database

COLLECTION_NAME = "customer_profiles"


def _collection() -> AsyncIOMotorCollection:
    return get_database()[COLLECTION_NAME]


def _ensure_self_access(user_id: str, principal: Principal) -> None:
    if principal.user_id != user_id:
        raise ApiError(
            status=403,
            code="forbidden",
            title="Forbidden",
            detail="Cannot access another user's profile",
        )


def _doc_to_profile(doc: dict[str, Any]) -> Profile:
    return Profile(
        user_id=doc["user_id"],
        lifecycle_stage=doc.get("lifecycle_stage"),
        vip_tier=doc.get("vip_tier"),
        scores=dict(doc.get("scores") or {}),
        consent=dict(doc.get("consent") or {}),
    )


def _profile_payload(body: Profile) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "user_id": body.user_id,
        "scores": body.scores,
        "consent": body.consent,
    }
    if body.lifecycle_stage is not None:
        payload["lifecycle_stage"] = body.lifecycle_stage
    if body.vip_tier is not None:
        payload["vip_tier"] = body.vip_tier
    return payload


def _diff_updated_fields(before: dict[str, Any] | None, after: dict[str, Any]) -> list[str]:
    if before is None:
        return sorted(after.keys())
    fields: set[str] = set()
    for key in ("lifecycle_stage", "vip_tier", "scores", "consent"):
        if before.get(key) != after.get(key):
            fields.add(key)
    return sorted(fields)


class ProfileService:
    async def get_profile(self, user_id: str, *, principal: Principal) -> tuple[Profile, str]:
        _ensure_self_access(user_id, principal)
        doc = await _collection().find_one(
            {"tenant_id": settings.tenant_default, "user_id": user_id}
        )
        if not doc:
            raise ApiError(status=404, code="not_found", title="Not found", detail="Profile not found")
        return _doc_to_profile(doc), format_etag(int(doc["version"]))

    async def upsert_profile(
        self,
        user_id: str,
        body: Profile,
        *,
        principal: Principal,
        if_match: str | None,
    ) -> tuple[Profile, str]:
        _ensure_self_access(user_id, principal)
        if body.user_id != user_id:
            raise ApiError(
                status=422,
                code="validation_error",
                title="Validation failed",
                detail="user_id in body must match path",
            )

        existing = await _collection().find_one(
            {"tenant_id": settings.tenant_default, "user_id": user_id}
        )
        now = utcnow()
        new_data = _profile_payload(body)

        if existing is not None:
            current_etag = format_etag(int(existing["version"]))
            if if_match is not None and if_match != current_etag:
                raise ApiError(
                    status=409,
                    code="conflict",
                    title="Conflict",
                    detail="If-Match does not match current profile version",
                )
            next_version = int(existing["version"]) + 1
            update_doc = {
                **new_data,
                "version": next_version,
                "updated_at": now,
            }
            result = await _collection().find_one_and_update(
                {
                    "tenant_id": settings.tenant_default,
                    "user_id": user_id,
                    "version": existing["version"],
                },
                {"$set": update_doc},
                return_document=ReturnDocument.AFTER,
            )
            if result is None:
                raise ApiError(
                    status=409,
                    code="conflict",
                    title="Conflict",
                    detail="Profile was modified concurrently",
                )
            doc = result
            before_snapshot = {
                "lifecycle_stage": existing.get("lifecycle_stage"),
                "vip_tier": existing.get("vip_tier"),
                "scores": existing.get("scores"),
                "consent": existing.get("consent"),
            }
        else:
            if if_match is not None:
                raise ApiError(
                    status=409,
                    code="conflict",
                    title="Conflict",
                    detail="If-Match provided but profile does not exist",
                )
            doc = {
                "tenant_id": settings.tenant_default,
                "user_id": user_id,
                **new_data,
                "version": 1,
                "created_at": now,
                "updated_at": now,
            }
            await _collection().insert_one(doc)
            before_snapshot = None

        updated_fields = _diff_updated_fields(before_snapshot, new_data)
        if not updated_fields:
            updated_fields = ["consent"] if "consent" in new_data else ["scores"]

        event_payload: dict[str, Any] = {
            "user_id": user_id,
            "updated_fields": updated_fields,
            "updated_at": now.isoformat(),
        }
        if body.lifecycle_stage is not None:
            event_payload["lifecycle_stage"] = body.lifecycle_stage
        if body.vip_tier is not None:
            event_payload["vip_tier"] = body.vip_tier

        await event_publisher.publish(
            event_type="profile.updated",
            tenant_id=settings.tenant_default,
            payload=event_payload,
            actor=EventActor(type="user", id=principal.user_id),
        )

        return _doc_to_profile(doc), format_etag(int(doc["version"]))


profile_service = ProfileService()
