"""API models for medical records, consent grants and the access log (profile.openapi.yaml v3.5)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

RecordType = Literal["lab_result", "imaging_report", "prescription", "referral_letter", "discharge_summary", "other"]
RECORD_TYPES: tuple[str, ...] = ("lab_result", "imaging_report", "prescription", "referral_letter", "discharge_summary", "other")
GranteeType = Literal["provider", "facility"]
GrantPurpose = Literal["consultation", "treatment", "second_opinion", "follow_up", "other"]
GrantStatus = Literal["active", "expired", "revoked"]
AccessAction = Literal["view", "download", "grant", "revoke", "delete", "denied"]
ActorKind = Literal["owner", "practitioner", "facility_staff", "other"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RecordShare(BaseModel):
    grant_id: str
    grantee_type: GranteeType
    grantee_id: str
    grantee_name: str
    purpose: GrantPurpose
    expires_at: datetime


class Record(BaseModel):
    id: str
    user_id: str
    title: str
    type: RecordType
    document_date: date | None
    note: str | None
    file_name: str
    content_type: str
    size_bytes: int
    created_at: datetime
    updated_at: datetime
    shares: list[RecordShare]


class RecordUsage(BaseModel):
    record_count: int
    total_bytes: int
    max_records: int
    max_total_bytes: int
    max_file_bytes: int


class RecordList(BaseModel):
    data: list[Record]
    usage: RecordUsage


class RecordUpdate(StrictModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    type: RecordType | None = None
    document_date: date | None = None
    note: str | None = Field(default=None, max_length=1000)


class GrantCreate(StrictModel):
    grantee_type: GranteeType
    grantee_id: str = Field(min_length=10, max_length=36)
    record_ids: list[str] = Field(min_length=1, max_length=50)
    purpose: GrantPurpose
    expires_in_days: int | None = Field(default=None, ge=1)
    appointment_id: str | None = Field(default=None, min_length=10, max_length=36)

    @field_validator("record_ids")
    @classmethod
    def _unique(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("record_ids must be unique")
        if any(not (10 <= len(v) <= 36) for v in value):
            raise ValueError("record_ids must be identifiers")
        return value


class GrantRevoke(StrictModel):
    record_ids: list[str] | None = Field(default=None, min_length=1, max_length=50)


class Grant(BaseModel):
    id: str
    user_id: str
    grantee_type: GranteeType
    grantee_id: str
    grantee_name: str
    record_ids: list[str]
    purpose: GrantPurpose
    appointment_id: str | None
    status: GrantStatus
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None


class GrantList(BaseModel):
    data: list[Grant]


class AccessActor(BaseModel):
    kind: ActorKind
    user_id: str | None


class AccessOrganisation(BaseModel):
    type: GranteeType
    id: str
    name: str | None


class AccessClient(BaseModel):
    network: str | None
    agent: str | None


class AccessLogEntry(BaseModel):
    id: str
    record_id: str
    grant_id: str | None
    action: AccessAction
    attempted: Literal["view", "download"] | None
    reason: str | None
    actor: AccessActor
    organisation: AccessOrganisation | None
    client: AccessClient
    occurred_at: datetime


class PageMeta(BaseModel):
    next_cursor: str | None
    limit: int
    has_more: bool


class AccessLogPage(BaseModel):
    data: list[AccessLogEntry]
    page: PageMeta


class SharedGrant(BaseModel):
    id: str
    patient_user_id: str
    grantee_type: GranteeType
    grantee_id: str
    purpose: GrantPurpose
    appointment_id: str | None
    record_count: int
    created_at: datetime
    expires_at: datetime


class SharedGrantList(BaseModel):
    data: list[SharedGrant]


class SharedRecord(BaseModel):
    id: str
    title: str
    type: RecordType
    document_date: date | None
    note: str | None
    file_name: str
    content_type: str
    size_bytes: int


class SharedGrantDetail(SharedGrant):
    records: list[SharedRecord]
