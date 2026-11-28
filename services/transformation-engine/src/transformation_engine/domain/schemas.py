from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from transformation_engine.domain.plan_templates import MAX_GOALS

GoalCode = Literal[
    "skin_health",
    "facial_aesthetics",
    "hair_restoration",
    "dental_smile",
    "weight_management",
    "fitness_recovery",
    "preventive_checkup",
    "longevity",
    "mental_wellbeing",
]

JourneyStatus = Literal[
    "draft",
    "onboarding",
    "active",
    "at_risk",
    "renewing",
    "completed",
    "churned",
]

MilestoneStatus = Literal["pending", "scheduled", "in_progress", "completed", "blocked"]

PhaseStatus = Literal["pending", "in_progress", "completed"]

NextActionType = Literal["book", "assess", "renew", "upsell", "adherence", "follow_up", "contact"]

NextActionPriority = Literal["low", "medium", "high", "urgent"]


class Money(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount_minor: int
    currency: str = "AED"


class CreateJourney(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    primary_goals: list[GoalCode] = Field(min_length=1, max_length=MAX_GOALS)
    target_completion: datetime | None = None

    @field_validator("primary_goals")
    @classmethod
    def _distinct_goals(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("primary_goals must not repeat a goal")
        return value


class Journey(BaseModel):
    id: str
    user_id: str
    primary_goals: list[str]
    status: JourneyStatus
    health_index: float
    started_at: str
    ltv_projection: Money | None = None


class Milestone(BaseModel):
    id: str
    title: str
    status: MilestoneStatus
    due_at: str | None = None
    code: str | None = None
    goal: str | None = None
    phase_id: str | None = None
    sequence: int = 0
    service_category: str | None = None
    appointment_id: str | None = None
    scheduled_at: str | None = None
    completed_at: str | None = None


class RoadmapPhase(BaseModel):
    id: str
    code: str | None = None
    name: str
    sequence: int
    status: PhaseStatus
    started_at: str | None = None
    completed_at: str | None = None
    milestones: list[Milestone] = Field(default_factory=list)


class Roadmap(BaseModel):
    journey_id: str
    phases: list[RoadmapPhase]


class NextAction(BaseModel):
    action_type: NextActionType
    priority: NextActionPriority
    due_at: str | None = None
    milestone_id: str | None = None
    milestone_code: str | None = None
    goal: str | None = None
    service_category: str | None = None


class PageMeta(BaseModel):
    limit: int
    has_more: bool
    next_cursor: str | None = None


class MilestoneListResponse(BaseModel):
    data: list[Milestone]
    page: PageMeta


class JourneyHealth(BaseModel):
    health_index: float = Field(ge=0, le=1)
    status: JourneyStatus
