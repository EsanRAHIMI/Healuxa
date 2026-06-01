from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, status
from healuxa_py_common.middleware.auth import Principal

from assessment_service.api.deps import require_assessment_permission
from assessment_service.domain.assessment_service import assessment_service
from assessment_service.domain.idempotency import validate_idempotency_key
from assessment_service.domain.schemas import Assessment, StartAssessmentRequest, SubmitAssessmentRequest

router = APIRouter(prefix="/v1/assessments", tags=["assessments"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=Assessment,
    operation_id="startAssessment",
)
async def start_assessment(
    body: StartAssessmentRequest,
    principal: Principal = Depends(require_assessment_permission("assessments:create")),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Assessment:
    validate_idempotency_key(idempotency_key)
    return await assessment_service.start_assessment(
        body,
        principal=principal,
        idempotency_key=idempotency_key,
    )


@router.get(
    "/{id}",
    response_model=Assessment,
    operation_id="getAssessment",
)
async def get_assessment(
    id: str,
    principal: Principal = Depends(require_assessment_permission("assessments:read")),
) -> Assessment:
    return await assessment_service.get_assessment(id, principal=principal)


@router.post(
    "/{id}/submit",
    response_model=Assessment,
    operation_id="submitAssessment",
)
async def submit_assessment(
    id: str,
    body: SubmitAssessmentRequest,
    principal: Principal = Depends(require_assessment_permission("assessments:write")),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Assessment:
    validate_idempotency_key(idempotency_key)
    return await assessment_service.submit_assessment(
        id,
        body,
        principal=principal,
        idempotency_key=idempotency_key,
    )
