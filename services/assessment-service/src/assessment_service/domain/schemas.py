from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

AssessmentKind = Literal["beauty", "body", "wellness", "longevity", "intake", "reassessment"]
AssessmentStatus = Literal["in_progress", "completed"]


class StartAssessmentRequest(BaseModel):
    user_id: str
    kind: AssessmentKind


class SubmitAssessmentRequest(BaseModel):
    responses: list[dict[str, Any]] = Field(default_factory=list)


class Assessment(BaseModel):
    id: str
    user_id: str
    kind: str
    status: AssessmentStatus
    recommended_goals: list[str] = Field(default_factory=list)
    scores: dict[str, float] = Field(default_factory=dict)
    responses: list[dict[str, Any]] | None = None
    completed_at: datetime | None = None
