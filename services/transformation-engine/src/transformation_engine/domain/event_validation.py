from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

ASSESSMENT_COMPLETED_TYPE = "assessment.completed"
ASSESSMENT_COMPLETED_VERSION = 1
ASSESSMENT_COMPLETED_PRODUCER = "assessment-service"
ASSESSMENT_COMPLETED_SCHEMA_REF = (
    "https://contracts.healuxa.com/events/assessment.schema.json#/$defs/AssessmentCompleted"
)

AssessmentKind = Literal["beauty", "body", "wellness", "longevity", "intake", "reassessment"]


class EventValidationError(ValueError):
    """Envelope or payload failed contract validation."""


class AssessmentCompletedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessment_id: str
    user_id: str
    kind: AssessmentKind
    completed_at: str
    recommended_goals: list[str] = Field(default_factory=list)
    scores: dict[str, float] = Field(default_factory=dict)

    @field_validator("assessment_id", "user_id")
    @classmethod
    def _non_empty_id(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("id must be non-empty")
        return value

    @field_validator("completed_at")
    @classmethod
    def _parse_completed_at(cls, value: str) -> str:
        normalized = value.replace("Z", "+00:00")
        datetime.fromisoformat(normalized)
        return value


class AssessmentCompletedEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    type: str
    version: int
    schema_ref: str
    occurred_at: str
    tenant_id: str
    producer: str
    payload: dict[str, Any]
    trace_id: str | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    actor: dict[str, Any] | None = None


def parse_assessment_completed_envelope(data: dict[str, Any]) -> AssessmentCompletedEnvelope:
    try:
        envelope = AssessmentCompletedEnvelope.model_validate(data)
    except ValidationError as exc:
        raise EventValidationError(str(exc)) from exc

    if envelope.type != ASSESSMENT_COMPLETED_TYPE:
        raise EventValidationError(f"unsupported event type: {envelope.type!r}")
    if envelope.version != ASSESSMENT_COMPLETED_VERSION:
        raise EventValidationError(f"unsupported event version: {envelope.version}")
    if envelope.schema_ref != ASSESSMENT_COMPLETED_SCHEMA_REF:
        raise EventValidationError(f"unexpected schema_ref: {envelope.schema_ref!r}")
    if envelope.producer != ASSESSMENT_COMPLETED_PRODUCER:
        raise EventValidationError(f"unexpected producer: {envelope.producer!r}")

    try:
        payload = AssessmentCompletedPayload.model_validate(envelope.payload)
    except ValidationError as exc:
        raise EventValidationError(str(exc)) from exc

    return envelope.model_copy(update={"payload": payload.model_dump(mode="json")})


def payload_is_empty_roadmap_seed(payload: dict[str, Any]) -> bool:
    goals = payload.get("recommended_goals") or []
    scores = payload.get("scores") or {}
    return len(goals) == 0 and len(scores) == 0
