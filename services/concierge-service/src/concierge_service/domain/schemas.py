from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CaseStatus = Literal[
    "submitted",
    "triaged",
    "assigned",
    "in_progress",
    "awaiting_customer",
    "arranged",
    "completed",
    "cancelled",
    "escalated",
]
CaseCategory = Literal["medical_travel", "specialist_search", "second_opinion_coordination", "logistics", "other"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CaseCreate(Strict):
    category: CaseCategory
    preferred_start_date: date | None = None
    preferred_end_date: date | None = None
    languages: list[str] = Field(default_factory=list, max_length=5)
    destination_city: str | None = Field(default=None, max_length=120)
    needs_note: str | None = Field(
        default=None,
        max_length=2000,
        description="Optional NON-CLINICAL logistics needs. Do not enter symptoms, diagnoses or medical history.",
    )

    @model_validator(mode="after")
    def _check(self) -> CaseCreate:
        import re

        for lang in self.languages:
            if not re.fullmatch(r"[a-z]{2,3}(-[A-Za-z]{2,4})?", lang):
                raise ValueError(f"invalid language tag: {lang!r}")
        if self.preferred_start_date and self.preferred_end_date and self.preferred_end_date < self.preferred_start_date:
            raise ValueError("preferred_end_date must not be before preferred_start_date")
        if self.needs_note is not None:
            self.needs_note = self.needs_note.strip() or None
        if self.destination_city is not None:
            self.destination_city = self.destination_city.strip() or None
        return self


class CaseOut(Strict):
    id: str
    customer_id: str
    category: CaseCategory
    status: CaseStatus
    preferred_start_date: date | None = None
    preferred_end_date: date | None = None
    languages: list[str]
    destination_city: str | None = None
    needs_note: str | None = None
    coordinator_id: str | None = None
    selected_option_id: str | None = None
    escalated_from: str | None = None
    first_response_due_at: datetime
    first_responded_at: datetime | None = None
    sla_breached: bool
    closed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class PageMeta(Strict):
    next_cursor: str | None = None
    limit: int
    has_more: bool


class CasePage(BaseModel):
    data: list[CaseOut]
    page: PageMeta


class TransitionRequest(Strict):
    to_status: CaseStatus
    reason: str | None = Field(default=None, max_length=500)


class AssignRequest(Strict):
    coordinator_id: str | None = Field(default=None, max_length=36)


class EscalateRequest(Strict):
    reason: str = Field(min_length=3, max_length=500)


class AuditOut(Strict):
    id: str
    action: Literal["submitted", "status_changed", "assigned", "option_proposed", "option_selected"]
    from_status: str | None = None
    to_status: str | None = None
    actor_id: str
    actor_role: Literal["customer", "coordinator", "supervisor"]
    reason: str | None = None
    subject_id: str | None = None
    created_at: datetime


class AuditPage(BaseModel):
    data: list[AuditOut]
    page: PageMeta


class NoteCreate(Strict):
    body: str = Field(min_length=1, max_length=4000)


class NoteOut(Strict):
    id: str
    case_id: str
    author_id: str
    body: str
    created_at: datetime


class NotePage(BaseModel):
    data: list[NoteOut]
    page: PageMeta


class OptionCreate(Strict):
    provider_id: str = Field(min_length=16, max_length=36)
    facility_id: str | None = Field(default=None, max_length=36)
    branch_id: str | None = Field(default=None, max_length=36)
    service_id: str | None = Field(default=None, max_length=36)
    label: str | None = Field(default=None, max_length=200)


class OptionOut(Strict):
    id: str
    case_id: str
    provider_id: str
    facility_id: str | None = None
    branch_id: str | None = None
    service_id: str | None = None
    label: str | None = None
    status: Literal["proposed", "selected", "not_selected"]
    proposed_by: str
    created_at: datetime


class OptionList(BaseModel):
    data: list[OptionOut]


class MessageCreate(Strict):
    body: str = Field(min_length=1, max_length=4000)


class MessageOut(Strict):
    id: str
    case_id: str
    sender_id: str
    sender_role: Literal["customer", "coordinator"]
    body: str
    read_at: datetime | None = None
    created_at: datetime


class MessagePage(BaseModel):
    data: list[MessageOut]
    page: PageMeta


class ReadRequest(Strict):
    up_to_message_id: str | None = None


class ReadResult(Strict):
    marked: int
