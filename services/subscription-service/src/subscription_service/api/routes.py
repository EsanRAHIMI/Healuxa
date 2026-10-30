from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Body, Depends, Header, Response
from healuxa_py_common.errors import ApiError
from healuxa_py_common.middleware.auth import Principal
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from subscription_service.api.deps import get_db, require_permission
from subscription_service.config import settings
from subscription_service.domain import memberships as m
from subscription_service.infra.models import Plan, Subscription


def memberships_enabled() -> None:
    if not settings.memberships_enabled:
        raise ApiError(status=404, code="not_found", title="Not found", detail="Memberships are not available")


router = APIRouter(prefix="/v1", dependencies=[Depends(memberships_enabled)])

Cycle = Literal["monthly", "quarterly", "annual"]


class EntitlementIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    quantity: int | None = Field(default=None, ge=0)


class PlanIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,63}$")
    name: str = Field(min_length=2, max_length=120)
    price_minor: int = Field(ge=100)
    currency: str = Field(default="AED", pattern=r"^[A-Z]{3}$")
    billing_cycle: Cycle
    credits: int | None = Field(default=None, ge=0)
    entitlements: list[EntitlementIn] = Field(default_factory=list, max_length=50)


class PlanPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=2, max_length=120)
    price_minor: int | None = Field(default=None, ge=100)
    credits: int | None = Field(default=None, ge=0)
    entitlements: list[EntitlementIn] | None = Field(default=None, max_length=50)
    status: Literal["active", "retired"] | None = None


class CreateSubscriptionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str | None = None
    plan_id: str = Field(min_length=2, max_length=64)
    billing_cycle: Cycle | None = None
    offer_id: str | None = None


class ChangePlanIn(BaseModel):
    to_plan_id: str = Field(min_length=2, max_length=64)
    offer_id: str | None = None


class CancelIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str | None = Field(default=None, max_length=500)


@router.get("/plans")
async def list_plans(db: Annotated[AsyncSession, Depends(get_db)]) -> list[dict]:
    rows = await db.scalars(select(Plan).where(Plan.tenant_id == settings.tenant_default, Plan.status == "active").order_by(Plan.price_minor))
    return [m.plan_view(p) for p in rows]


@router.post("/plans", status_code=201)
async def create_plan(
    body: PlanIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_permission("subscriptions:manage"))],
) -> dict:
    if body.currency != settings.currency:
        raise m.unprocessable(f"Only {settings.currency} is supported", "currency")
    plan = Plan(tenant_id=principal.tenant_id, created_by=principal.user_id, **{**body.model_dump(), "entitlements": [e.model_dump() for e in body.entitlements]})
    db.add(plan)
    try:
        await db.commit()
    except IntegrityError:
        raise m.conflict("Plan id already exists") from None
    return m.plan_view(plan)


@router.patch("/plans/{plan_id}")
async def update_plan(
    plan_id: str,
    body: PlanPatch,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_permission("subscriptions:manage"))],
) -> dict:
    plan = await db.get(Plan, (principal.tenant_id, plan_id))
    if plan is None:
        raise m.not_found("Plan")
    changes = body.model_dump(exclude_unset=True)
    if "entitlements" in changes:
        changes["entitlements"] = [e.model_dump() for e in body.entitlements or []]
    for key, value in changes.items():
        setattr(plan, key, value)
    plan.updated_at = datetime.now(UTC)
    await db.commit()
    return m.plan_view(plan)


@router.get("/subscriptions")
async def list_subscriptions(
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_permission("subscriptions:read"))],
) -> dict:
    rows = await db.scalars(
        select(Subscription).where(Subscription.tenant_id == principal.tenant_id, Subscription.user_id == principal.user_id).order_by(Subscription.id.desc())
    )
    return {"data": [m.subscription_view(s) for s in rows]}


@router.post("/subscriptions", status_code=201)
async def create_subscription(
    body: CreateSubscriptionIn,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_permission("subscriptions:create"))],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> dict:
    if not idempotency_key or not 8 <= len(idempotency_key) <= 128:
        raise ApiError(status=400, code="validation_error", title="Bad request", detail="Idempotency-Key header (8-128 chars) is required")
    sub, _ = await m.create_subscription(db, principal, body.model_dump(exclude_none=True), idempotency_key)
    await db.commit()
    response.headers["Location"] = f"/v1/subscriptions/{sub.id}"
    return m.subscription_view(sub)


@router.get("/subscriptions/me/entitlements")
async def get_my_entitlements(
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_permission("subscriptions:read"))],
) -> dict:
    return await m.entitlements(db, principal)


@router.get("/subscriptions/{sub_id}")
async def get_subscription(
    sub_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_permission("subscriptions:read"))],
) -> dict:
    return m.subscription_view(await m.visible_subscription(db, principal, sub_id))


@router.post("/subscriptions/{sub_id}/change-plan")
async def change_plan(
    sub_id: str,
    body: ChangePlanIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_permission("subscriptions:write"))],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> dict:
    sub = await m.change_plan(db, principal, sub_id, body.to_plan_id, body.offer_id, if_match)
    await db.commit()
    return m.subscription_view(sub)


@router.post("/subscriptions/{sub_id}/cancel")
async def cancel_subscription(
    sub_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_permission("subscriptions:write"))],
    body: Annotated[CancelIn | None, Body()] = None,
) -> dict:
    sub = await m.cancel(db, principal, sub_id, body.reason if body else None)
    await db.commit()
    return m.subscription_view(sub)
