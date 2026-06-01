from __future__ import annotations

from typing import Any

from healuxa_py_common.errors import ApiError
from healuxa_py_common.events.envelope import EventActor
from healuxa_py_common.middleware.auth import Principal
from motor.motor_asyncio import AsyncIOMotorCollection
from ulid import ULID

from assessment_service.config import settings
from assessment_service.domain.idempotency import (
    hash_request_body,
    read_idempotent_response,
    store_idempotent_response,
)
from assessment_service.domain.schemas import Assessment, StartAssessmentRequest, SubmitAssessmentRequest
from assessment_service.domain.security import utcnow
from assessment_service.events.publisher import event_publisher
from assessment_service.infra.mongo import get_database

COLLECTION_NAME = "assessments"


def _collection() -> AsyncIOMotorCollection:
    return get_database()[COLLECTION_NAME]


def _ensure_owner(doc: dict[str, Any], principal: Principal) -> None:
    if doc.get("user_id") != principal.user_id:
        raise ApiError(
            status=403,
            code="forbidden",
            title="Forbidden",
            detail="Cannot access another user's assessment",
        )


def _doc_to_assessment(doc: dict[str, Any]) -> Assessment:
    return Assessment(
        id=doc["_id"],
        user_id=doc["user_id"],
        kind=doc["kind"],
        status=doc["status"],
        recommended_goals=list(doc.get("recommended_goals") or []),
        scores=dict(doc.get("scores") or {}),
        completed_at=doc.get("completed_at"),
    )


class AssessmentService:
    async def start_assessment(
        self,
        body: StartAssessmentRequest,
        *,
        principal: Principal,
        idempotency_key: str | None,
    ) -> Assessment:
        if body.user_id != principal.user_id:
            raise ApiError(
                status=403,
                code="forbidden",
                title="Forbidden",
                detail="Cannot start an assessment for another user",
            )

        body_hash = hash_request_body(body.model_dump(mode="json"))
        if idempotency_key:
            cached = await read_idempotent_response(idempotency_key, request_hash=body_hash)
            if cached:
                return Assessment(**cached)

        assessment_id = str(ULID())
        now = utcnow()
        tenant_id = settings.tenant_default
        doc = {
            "_id": assessment_id,
            "tenant_id": tenant_id,
            "user_id": principal.user_id,
            "kind": body.kind,
            "status": "in_progress",
            "responses": [],
            "recommended_goals": [],
            "scores": {},
            "created_at": now,
            "updated_at": now,
            "completed_at": None,
        }
        await _collection().insert_one(doc)
        response = _doc_to_assessment(doc)

        if idempotency_key:
            await store_idempotent_response(
                idempotency_key,
                request_hash=body_hash,
                status_code=201,
                response_body=response.model_dump(mode="json"),
            )

        return response

    async def get_assessment(
        self,
        assessment_id: str,
        *,
        principal: Principal,
    ) -> Assessment:
        doc = await _collection().find_one(
            {"_id": assessment_id, "tenant_id": settings.tenant_default},
        )
        if not doc:
            raise ApiError(status=404, code="not_found", title="Not found", detail="Assessment not found")
        _ensure_owner(doc, principal)
        return _doc_to_assessment(doc)

    async def submit_assessment(
        self,
        assessment_id: str,
        body: SubmitAssessmentRequest,
        *,
        principal: Principal,
        idempotency_key: str | None,
    ) -> Assessment:
        request_hash = hash_request_body(
            {"assessment_id": assessment_id, **body.model_dump(mode="json")},
        )
        if idempotency_key:
            cached = await read_idempotent_response(idempotency_key, request_hash=request_hash)
            if cached:
                return Assessment(**cached)

        doc = await _collection().find_one(
            {"_id": assessment_id, "tenant_id": settings.tenant_default},
        )
        if not doc:
            raise ApiError(status=404, code="not_found", title="Not found", detail="Assessment not found")
        _ensure_owner(doc, principal)

        if doc.get("status") == "completed":
            raise ApiError(
                status=409,
                code="conflict",
                title="Conflict",
                detail="Assessment already completed",
            )

        now = utcnow()
        # Phase later: populate recommended_goals and scores only through approved AI/rule engine/orchestrator. Do not infer in scaffold.
        recommended_goals: list[str] = []
        scores: dict[str, float] = {}

        await _collection().update_one(
            {"_id": assessment_id, "tenant_id": settings.tenant_default},
            {
                "$set": {
                    "responses": body.responses,
                    "status": "completed",
                    "completed_at": now,
                    "recommended_goals": recommended_goals,
                    "scores": scores,
                    "updated_at": now,
                }
            },
        )

        await event_publisher.publish(
            event_type="assessment.completed",
            tenant_id=settings.tenant_default,
            payload={
                "assessment_id": assessment_id,
                "user_id": doc["user_id"],
                "kind": doc["kind"],
                "recommended_goals": recommended_goals,
                "scores": scores,
                "completed_at": now.isoformat(),
            },
            actor=EventActor(type="user", id=principal.user_id),
        )

        updated = await _collection().find_one(
            {"_id": assessment_id, "tenant_id": settings.tenant_default},
        )
        assert updated is not None
        response = _doc_to_assessment(updated)

        if idempotency_key:
            await store_idempotent_response(
                idempotency_key,
                request_hash=request_hash,
                status_code=200,
                response_body=response.model_dump(mode="json"),
            )

        return response


assessment_service = AssessmentService()
