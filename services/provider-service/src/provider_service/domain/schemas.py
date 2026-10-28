"""Request/response models per packages/api-contracts/openapi/provider.openapi.yaml (v3.4)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ProviderType = Literal["doctor", "clinic", "therapist", "trainer", "nutritionist", "pharmacy", "brand", "home_visit"]
ProviderStatus = Literal["pending", "active", "suspended", "offboarded"]
VerificationStatus = Literal["unverified", "under_review", "verified", "rejected"]
CredentialKind = Literal["professional_license", "board_certification", "malpractice_insurance", "other"]
FacilityType = Literal[
    "clinic", "hospital", "medical_center", "day_surgery", "diagnostic_center", "pharmacy", "wellness_center"
]
StaffRole = Literal["facility_admin", "scheduler", "billing"]
ExceptionReason = Literal["leave", "public_holiday", "training", "other"]

HHMM = r"^([01][0-9]|2[0-3]):[0-5][0-9]$"
HHMM_END = r"^([01][0-9]|2[0-3]):[0-5][0-9]$|^24:00$"
LANGUAGE_TAGS = {"en", "ar", "fa", "fr", "de"}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _check_localized(value: dict[str, str] | None) -> dict[str, str] | None:
    if value is None:
        return value
    unknown = set(value) - LANGUAGE_TAGS
    if unknown:
        raise ValueError(f"unsupported language tags: {sorted(unknown)}")
    if any(len(text) > 4000 for text in value.values()):
        raise ValueError("localized text exceeds 4000 characters")
    return value


def to_minutes(hhmm: str) -> int:
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def from_minutes(total: int) -> str:
    return f"{total // 60:02d}:{total % 60:02d}"


# ── Providers ────────────────────────────────────────────────────────────────────────────────


class ProviderInput(StrictModel):
    type: ProviderType
    display_name: str = Field(min_length=2, max_length=160)
    title: str | None = Field(default=None, max_length=160)
    bio: dict[str, str] | None = None
    specialties: list[str] = Field(min_length=1, max_length=20)
    languages: list[str] = Field(min_length=1, max_length=20)

    _bio = field_validator("bio")(_check_localized)


class ProviderPatch(StrictModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=160)
    title: str | None = Field(default=None, max_length=160)
    bio: dict[str, str] | None = None
    specialties: list[str] | None = Field(default=None, min_length=1, max_length=20)
    languages: list[str] | None = Field(default=None, min_length=1, max_length=20)

    _bio = field_validator("bio")(_check_localized)


class StatusChange(StrictModel):
    status: ProviderStatus
    reason: str = Field(min_length=3, max_length=1000)


class VerifiedCredentialSummary(BaseModel):
    kind: CredentialKind
    issuing_authority: str
    valid_until: date | None


class Provider(BaseModel):
    id: str
    type: ProviderType
    display_name: str
    title: str | None
    bio: dict[str, str]
    specialties: list[str]
    languages: list[str]
    quality_score: float | None
    success_score: float | None
    status: ProviderStatus
    verification_status: VerificationStatus
    verified_credentials: list[VerifiedCredentialSummary]
    user_id: str | None = None
    version: int
    created_at: datetime
    updated_at: datetime


# ── Credentials ──────────────────────────────────────────────────────────────────────────────


class CredentialInput(StrictModel):
    kind: CredentialKind
    issuing_authority: str = Field(min_length=2, max_length=64)
    jurisdiction: str | None = Field(default=None, max_length=16)
    number: str = Field(min_length=2, max_length=64)
    valid_from: date | None = None
    valid_until: date | None = None
    document_ref: str | None = Field(default=None, max_length=512)

    @model_validator(mode="after")
    def _dates(self) -> CredentialInput:
        if self.valid_from and self.valid_until and self.valid_until < self.valid_from:
            raise ValueError("valid_until must not precede valid_from")
        return self


class Credential(BaseModel):
    id: str
    provider_id: str
    kind: CredentialKind
    issuing_authority: str
    jurisdiction: str | None
    number: str
    valid_from: date | None
    valid_until: date | None
    document_ref: str | None
    status: Literal["submitted", "verified", "rejected", "expired"]
    review_note: str | None
    reviewed_at: datetime | None


class ReviewDecision(StrictModel):
    decision: Literal["verify", "reject"]
    note: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _note_on_reject(self) -> ReviewDecision:
        if self.decision == "reject" and not (self.note and self.note.strip()):
            raise ValueError("a note is required when rejecting")
        return self


# ── Facilities ───────────────────────────────────────────────────────────────────────────────


class FacilityInput(StrictModel):
    type: FacilityType
    name: str = Field(min_length=2, max_length=200)
    description: dict[str, str] | None = None
    license_authority: str = Field(min_length=2, max_length=64)
    license_number: str = Field(min_length=2, max_length=64)
    website: str | None = Field(default=None, max_length=300)
    phone: str | None = Field(default=None, max_length=32)

    _description = field_validator("description")(_check_localized)


class FacilityPatch(StrictModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: dict[str, str] | None = None
    website: str | None = Field(default=None, max_length=300)
    phone: str | None = Field(default=None, max_length=32)

    _description = field_validator("description")(_check_localized)


class Facility(BaseModel):
    id: str
    type: FacilityType
    name: str
    description: dict[str, str]
    license_authority: str | None = None
    license_number: str | None = None
    website: str | None
    phone: str | None
    status: ProviderStatus
    verification_status: VerificationStatus
    created_at: datetime


class BranchInput(StrictModel):
    name: str = Field(min_length=2, max_length=200)
    address_line: str = Field(min_length=2, max_length=300)
    city: str = Field(min_length=2, max_length=100)
    emirate: str | None = Field(default=None, max_length=64)
    country: str = Field(pattern=r"^[A-Z]{2}$")
    timezone: str = Field(max_length=64)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    phone: str | None = Field(default=None, max_length=32)

    @field_validator("timezone")
    @classmethod
    def _valid_zone(cls, value: str) -> str:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("unknown IANA timezone") from exc
        return value


class Branch(BaseModel):
    id: str
    facility_id: str
    name: str
    address_line: str
    city: str
    emirate: str | None
    country: str
    timezone: str
    latitude: float | None
    longitude: float | None
    phone: str | None
    status: Literal["active", "closed"]


class TimeWindow(StrictModel):
    weekday: int = Field(ge=0, le=6)
    start: str = Field(pattern=HHMM)
    end: str = Field(pattern=HHMM_END)

    @model_validator(mode="after")
    def _ordered(self) -> TimeWindow:
        if to_minutes(self.start) >= to_minutes(self.end):
            raise ValueError("start must be before end")
        return self


class OperatingHoursInput(StrictModel):
    windows: list[TimeWindow] = Field(max_length=28)

    @model_validator(mode="after")
    def _no_overlap(self) -> OperatingHoursInput:
        by_day: dict[int, list[tuple[int, int]]] = {}
        for window in self.windows:
            by_day.setdefault(window.weekday, []).append((to_minutes(window.start), to_minutes(window.end)))
        for spans in by_day.values():
            spans.sort()
            for (_, prev_end), (next_start, _) in zip(spans, spans[1:]):
                if next_start < prev_end:
                    raise ValueError("operating hours windows overlap")
        return self


class OperatingHours(BaseModel):
    branch_id: str
    timezone: str
    windows: list[TimeWindow]


class StaffMemberInput(StrictModel):
    user_id: str = Field(min_length=16, max_length=36)
    role: StaffRole


class StaffMember(BaseModel):
    facility_id: str
    user_id: str
    role: StaffRole
    created_at: datetime


# ── Affiliations ─────────────────────────────────────────────────────────────────────────────


class AffiliationInput(StrictModel):
    provider_id: str
    branch_id: str


class AffiliationDecision(StrictModel):
    decision: Literal["approve", "decline", "end"]


class Affiliation(BaseModel):
    id: str
    provider_id: str
    facility_id: str
    branch_id: str
    status: Literal["pending", "active", "declined", "ended"]
    initiated_by: Literal["provider", "facility"]
    decided_at: datetime | None
    created_at: datetime


# ── Catalog ──────────────────────────────────────────────────────────────────────────────────


class Money(BaseModel):
    amount_minor: int
    currency: str


class ServiceOfferingInput(StrictModel):
    branch_id: str
    category: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=2, max_length=200)
    description: dict[str, str] | None = None
    duration_minutes: int = Field(ge=5, le=720)
    buffer_minutes: int = Field(default=0, ge=0, le=240)
    mode: Literal["in_person", "home_visit"] = "in_person"
    price_type: Literal["fixed", "from", "on_request"]
    professional_fee_minor: int | None = Field(default=None, ge=0)
    facility_fee_minor: int | None = Field(default=None, ge=0)
    currency: str = Field(default="AED", pattern=r"^[A-Z]{3}$")

    _description = field_validator("description")(_check_localized)

    @model_validator(mode="after")
    def _price(self) -> ServiceOfferingInput:
        if self.price_type == "on_request":
            if self.professional_fee_minor is not None or self.facility_fee_minor is not None:
                raise ValueError("on_request offerings must not carry fees")
        elif self.professional_fee_minor is None:
            raise ValueError("professional_fee_minor is required for fixed and from prices")
        return self


class ServiceOfferingPatch(StrictModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: dict[str, str] | None = None
    duration_minutes: int | None = Field(default=None, ge=5, le=720)
    buffer_minutes: int | None = Field(default=None, ge=0, le=240)
    price_type: Literal["fixed", "from", "on_request"] | None = None
    professional_fee_minor: int | None = Field(default=None, ge=0)
    facility_fee_minor: int | None = Field(default=None, ge=0)
    status: Literal["draft", "active", "retired"] | None = None

    _description = field_validator("description")(_check_localized)


class ServiceOffering(BaseModel):
    id: str
    provider_id: str
    facility_id: str
    branch_id: str
    category: str
    name: str
    description: dict[str, str]
    duration_minutes: int
    buffer_minutes: int
    mode: Literal["in_person", "home_visit"]
    price_type: Literal["fixed", "from", "on_request"]
    price: Money | None
    professional_fee: Money | None
    facility_fee: Money | None
    status: Literal["draft", "active", "retired"]


# ── Availability ─────────────────────────────────────────────────────────────────────────────


class AvailabilityRuleInput(StrictModel):
    branch_id: str
    weekday: int = Field(ge=0, le=6)
    start: str = Field(pattern=HHMM)
    end: str = Field(pattern=HHMM_END)
    effective_from: date
    effective_until: date | None = None

    @model_validator(mode="after")
    def _ordered(self) -> AvailabilityRuleInput:
        if to_minutes(self.start) >= to_minutes(self.end):
            raise ValueError("start must be before end")
        if self.effective_until and self.effective_until < self.effective_from:
            raise ValueError("effective_until must not precede effective_from")
        return self


class AvailabilityRule(BaseModel):
    id: str
    provider_id: str
    branch_id: str
    timezone: str
    weekday: int
    start: str
    end: str
    effective_from: date
    effective_until: date | None


class AvailabilityExceptionInput(StrictModel):
    branch_id: str | None = None
    starts_at: datetime
    ends_at: datetime
    reason: ExceptionReason

    @model_validator(mode="after")
    def _range(self) -> AvailabilityExceptionInput:
        if self.starts_at.tzinfo is None or self.ends_at.tzinfo is None:
            raise ValueError("starts_at and ends_at must include a UTC offset")
        if self.starts_at >= self.ends_at:
            raise ValueError("starts_at must be before ends_at")
        if (self.ends_at - self.starts_at).days > 366:
            raise ValueError("an exception may span at most 366 days")
        return self


class AvailabilityException(BaseModel):
    id: str
    provider_id: str
    branch_id: str | None
    starts_at: datetime
    ends_at: datetime
    reason: ExceptionReason


class PageMeta(BaseModel):
    next_cursor: str | None
    limit: int
    has_more: bool
