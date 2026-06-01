from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

LifecycleStage = Literal["lead", "onboarding", "active", "at_risk", "churned", "reactivated"]
VipTier = Literal["none", "silver", "gold", "black"]


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    lifecycle_stage: LifecycleStage | None = None
    vip_tier: VipTier | None = None
    scores: dict[str, float] = Field(default_factory=dict)
    consent: dict[str, Any] = Field(default_factory=dict)
