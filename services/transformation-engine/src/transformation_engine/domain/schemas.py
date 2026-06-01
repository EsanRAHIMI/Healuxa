from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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

NextActionType = Literal["book", "assess", "renew", "upsell", "adherence", "follow_up", "contact"]

NextActionPriority = Literal["low", "medium", "high", "urgent"]


class Money(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount_minor: int
    currency: str = "AED"


class CreateJourney(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    primary_goals: list[str] = Field(min_length=1)
    target_completion: datetime | None = None


class Journey(BaseModel):
    id: str
    user_id: str
    primary_goals: list[str]
    status: JourneyStatus
    health_index: float
    started_at: str
    ltv_projection: Money | None = None


class Roadmap(BaseModel):
    journey_id: str
    phases: list[dict]


class Milestone(BaseModel):
    id: str
    title: str
    status: MilestoneStatus
    due_at: str | None = None


class NextAction(BaseModel):
    action_type: NextActionType
    priority: NextActionPriority
    due_at: str | None = None


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
