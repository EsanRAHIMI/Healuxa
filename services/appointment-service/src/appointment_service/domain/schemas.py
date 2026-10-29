"""API models per appointment.openapi.yaml v3.4."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

AppointmentStatus = Literal[
    "held",
    "requested",
    "confirmed",
    "checked_in",
    "completed",
    "cancelled",
    "declined",
    "no_show",
    "expired",
    "rescheduled",
]
PaymentStatus = Literal["not_required", "pending", "authorized", "captured", "refunded"]
Party = Literal["customer", "provider", "facility", "platform", "system"]
Transition = Literal["submit", "accept", "decline", "cancel", "check_in", "complete", "no_show"]
ReasonCode = Literal[
    "no_capacity",
    "out_of_scope",
    "schedule_conflict",
    "customer_request",
    "provider_unavailable",
    "facility_closed",
    "other",
]
DECLINE_REASONS = ("no_capacity", "out_of_scope", "schedule_conflict", "other")
CANCEL_REASONS = ("customer_request", "provider_unavailable", "facility_closed", "other")

Id = str


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Slot(BaseModel):
    scheduled_at: datetime
    ends_at: datetime
    local_start: str
    local_end: str


class SlotList(BaseModel):
    service_id: str
    provider_id: str
    branch_id: str
    timezone: str
    duration_minutes: int
    buffer_minutes: int
    from_: date = Field(serialization_alias="from")
    to: date
    slots: list[Slot]


class CreateAppointment(StrictModel):
    service_id: Id = Field(min_length=10, max_length=36)
    scheduled_at: AwareDatetime
    milestone_id: Id | None = Field(default=None, min_length=10, max_length=36)
    channel: Literal["app", "web", "whatsapp", "concierge"] | None = None
    user_id: Id | None = Field(default=None, min_length=10, max_length=36)


class TransitionRequest(StrictModel):
    transition: Transition
    reason_code: ReasonCode | None = None
    reason: str | None = Field(default=None, max_length=500)
    party: Literal["customer", "provider"] | None = None


class RescheduleRequest(StrictModel):
    scheduled_at: AwareDatetime
    reason: str | None = Field(default=None, max_length=500)


class Money(BaseModel):
    amount_minor: int
    currency: str


class Reminder(BaseModel):
    id: str
    offset_minutes: int
    due_at: datetime
    status: Literal["scheduled", "dispatched", "skipped", "cancelled"]


class StatusTransition(BaseModel):
    id: str
    appointment_id: str
    from_status: AppointmentStatus | None
    to_status: AppointmentStatus
    actor_type: Party
    actor_id: str | None
    reason_code: str | None
    reason: str | None
    occurred_at: datetime


class Appointment(BaseModel):
    id: str
    user_id: str
    provider_id: str
    facility_id: str
    branch_id: str
    service_id: str
    milestone_id: str | None
    status: AppointmentStatus
    scheduled_at: datetime
    ends_at: datetime
    local_start: str
    timezone: str
    duration_minutes: int
    buffer_minutes: int
    service_name: str | None
    price: Money | None
    payment_status: PaymentStatus
    channel: str | None
    hold_expires_at: datetime | None
    requested_at: datetime | None
    confirmed_at: datetime | None
    checked_in_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    cancelled_by: Party | None
    decline_reason: str | None
    no_show_party: str | None
    rescheduled_from_id: str | None
    rescheduled_to_id: str | None
    reminders: list[Reminder]
    version: int
    created_at: datetime
