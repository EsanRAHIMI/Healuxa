"""Plans, memberships, entitlements, and the reaction to payment-service billing events.

Money never moves here. Status changes from incomplete/past_due to active only on payment-service's
payment.succeeded (verified processor truth); renewal/churn follow payment.* events.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from healuxa_py_common.errors import ApiError
from healuxa_py_common.events.envelope import EventActor
from healuxa_py_common.middleware.auth import Principal
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from subscription_service.events.publisher import money, publish
from subscription_service.infra.models import OPEN_STATUSES, ConsumedEvent, Plan, Subscription

MANAGE = "subscriptions:manage"
CYCLE_MONTHS = {"monthly": 1, "quarterly": 3, "annual": 12}


def not_found(what: str) -> ApiError:
    return ApiError(status=404, code="not_found", title="Not found", detail=f"{what} not found")


def conflict(detail: str, code: str = "conflict") -> ApiError:
    return ApiError(status=409, code=code, title="Conflict", detail=detail)  # type: ignore[arg-type]


def unprocessable(detail: str, field: str | None = None) -> ApiError:
    errors = [{"field": field, "code": "invalid", "message": detail}] if field else None
    return ApiError(status=422, code="unprocessable", title="Unprocessable", detail=detail, errors=errors)


def actor(principal: Principal) -> EventActor:
    return EventActor(type="user", id=principal.user_id)


def plan_view(plan: Plan) -> dict[str, Any]:
    return {
        "id": plan.id,
        "name": plan.name,
        "price": money(plan.price_minor, plan.currency),
        "billing_cycle": plan.billing_cycle,
        "credits": plan.credits,
        "entitlements": plan.entitlements,
        "status": plan.status,
    }


def subscription_view(sub: Subscription) -> dict[str, Any]:
    return {
        "id": sub.id,
        "user_id": sub.user_id,
        "plan_id": sub.plan_id,
        "status": sub.status,
        "price": money(sub.price_minor, sub.currency),
        "billing_cycle": sub.billing_cycle,
        "credits_remaining": sub.credits_remaining,
        "cancel_at_period_end": sub.cancel_at_period_end,
        "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
        "version": sub.version,
        "created_at": sub.created_at.isoformat() if sub.created_at else None,
    }


async def visible_subscription(db: AsyncSession, principal: Principal, sub_id: str, *, lock: bool = False) -> Subscription:
    query = select(Subscription).where(Subscription.id == sub_id, Subscription.tenant_id == principal.tenant_id)
    if lock:
        query = query.with_for_update()
    sub = await db.scalar(query)
    if sub is None or (sub.user_id != principal.user_id and MANAGE not in principal.permissions):
        raise not_found("Subscription")
    return sub


async def _status(db: AsyncSession, sub: Subscription, to_status: str) -> None:
    if sub.status == to_status:
        return
    previous, sub.status = sub.status, to_status
    sub.version += 1
    sub.updated_at = datetime.now(UTC)
    await publish(
        db,
        "subscription.status_changed",
        sub.tenant_id,
        {"subscription_id": sub.id, "user_id": sub.user_id, "plan_id": sub.plan_id, "from_status": previous, "to_status": to_status,
         "changed_at": sub.updated_at.isoformat()},
    )


async def create_subscription(db: AsyncSession, principal: Principal, body: dict[str, Any], key: str) -> tuple[Subscription, bool]:
    if body.get("user_id") and body["user_id"] != principal.user_id:
        raise ApiError(status=403, code="forbidden", title="Forbidden", detail="Subscriptions are created by the member")
    digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    existing = await db.scalar(
        select(Subscription).where(
            Subscription.tenant_id == principal.tenant_id, Subscription.user_id == principal.user_id, Subscription.creation_key == key
        )
    )
    if existing is not None:
        if existing.request_hash != digest:
            raise conflict("Idempotency-Key reused with a different request", code="idempotency_conflict")
        return existing, False
    plan = await db.get(Plan, (principal.tenant_id, body["plan_id"]))
    if plan is None or plan.status != "active":
        raise not_found("Plan")
    if body.get("billing_cycle") and body["billing_cycle"] != plan.billing_cycle:
        raise unprocessable(f"Plan is billed {plan.billing_cycle}", "billing_cycle")
    sub = Subscription(
        id=str(ULID()),
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        plan_id=plan.id,
        status="incomplete",
        price_minor=plan.price_minor,
        currency=plan.currency,
        billing_cycle=plan.billing_cycle,
        credits_remaining=plan.credits,
        creation_key=key,
        request_hash=digest,
    )
    db.add(sub)
    try:
        await db.flush()
    except IntegrityError:
        raise conflict("You already have an open membership") from None
    await publish(
        db,
        "subscription.created",
        sub.tenant_id,
        {"subscription_id": sub.id, "user_id": sub.user_id, "plan_id": sub.plan_id, "price": money(sub.price_minor, sub.currency),
         "billing_cycle": sub.billing_cycle, "status": "incomplete", "started_at": datetime.now(UTC).isoformat()},
        actor(principal),
    )
    return sub, True


def _monthly(price_minor: int, cycle: str) -> int:
    return price_minor // CYCLE_MONTHS[cycle]


async def change_plan(db: AsyncSession, principal: Principal, sub_id: str, to_plan_id: str, offer_id: str | None, if_match: str | None) -> Subscription:
    sub = await visible_subscription(db, principal, sub_id, lock=True)
    if if_match and if_match.strip('W/"') != str(sub.version):
        raise conflict("Subscription changed; reload and retry")
    if sub.status not in {"active", "past_due"}:
        raise conflict(f"Only active memberships can change plan (status {sub.status})")
    plan = await db.get(Plan, (sub.tenant_id, to_plan_id))
    if plan is None or plan.status != "active":
        raise not_found("Plan")
    if plan.id == sub.plan_id:
        raise unprocessable("Already on this plan", "to_plan_id")
    old_monthly = _monthly(sub.price_minor, sub.billing_cycle)
    new_monthly = _monthly(plan.price_minor, plan.billing_cycle)
    event = "subscription.upgraded" if new_monthly >= old_monthly else "subscription.downgraded"
    from_plan = sub.plan_id
    sub.plan_id, sub.price_minor, sub.billing_cycle, sub.credits_remaining = plan.id, plan.price_minor, plan.billing_cycle, plan.credits
    sub.version += 1
    sub.updated_at = datetime.now(UTC)
    payload = {
        "subscription_id": sub.id,
        "user_id": sub.user_id,
        "from_plan_id": from_plan,
        "to_plan_id": plan.id,
        "mrr_delta": money(new_monthly - old_monthly, sub.currency),
        "price": money(plan.price_minor, plan.currency),
        "billing_cycle": plan.billing_cycle,
        "changed_at": sub.updated_at.isoformat(),
    }
    if event == "subscription.upgraded" and offer_id:
        payload["triggered_by_offer_id"] = offer_id
    await publish(db, event, sub.tenant_id, payload, actor(principal))
    return sub


async def cancel(db: AsyncSession, principal: Principal, sub_id: str, reason: str | None) -> Subscription:
    sub = await visible_subscription(db, principal, sub_id, lock=True)
    if sub.status not in OPEN_STATUSES:
        raise conflict(f"Membership is already {sub.status}")
    if sub.cancel_at_period_end:
        raise conflict("Cancellation is already scheduled")
    sub.cancel_reason = reason
    if sub.status == "incomplete":
        await _status(db, sub, "cancelled")  # never paid: nothing to run out
    else:
        sub.cancel_at_period_end = True
        sub.version += 1
    await publish(
        db,
        "subscription.cancellation_scheduled",
        sub.tenant_id,
        {"subscription_id": sub.id, "user_id": sub.user_id, "plan_id": sub.plan_id,
         "cancel_at": sub.current_period_end.isoformat() if sub.current_period_end else None, "reason": reason,
         "requested_at": datetime.now(UTC).isoformat()},
        actor(principal),
    )
    return sub


async def entitlements(db: AsyncSession, principal: Principal) -> dict[str, Any]:
    sub = await db.scalar(
        select(Subscription).where(
            Subscription.tenant_id == principal.tenant_id, Subscription.user_id == principal.user_id, Subscription.status == "active"
        )
    )
    if sub is None:
        return {"user_id": principal.user_id, "subscription_id": None, "plan_id": None, "status": None, "credits": None,
                "valid_until": None, "entitlements": []}
    plan = await db.get(Plan, (sub.tenant_id, sub.plan_id))
    return {
        "user_id": principal.user_id,
        "subscription_id": sub.id,
        "plan_id": sub.plan_id,
        "status": sub.status,
        "credits": sub.credits_remaining,
        "valid_until": sub.current_period_end.isoformat() if sub.current_period_end else None,
        "entitlements": plan.entitlements if plan else [],
    }


# ── payment-service events ───────────────────────────────────────────────────


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


async def handle_payment_event(db: AsyncSession, envelope: dict[str, Any]) -> str:
    """Apply one payment.* event (caller commits). Idempotent on event_id."""
    inserted = await db.scalar(
        insert(ConsumedEvent).values(event_id=envelope["event_id"], event_type=envelope["type"]).on_conflict_do_nothing().returning(ConsumedEvent.event_id)
    )
    if inserted is None:
        return "duplicate"
    payload = envelope["payload"]
    sub_id = payload.get("subscription_id")
    if not sub_id:
        return "ignored"
    sub = await db.scalar(
        select(Subscription).where(Subscription.id == sub_id, Subscription.tenant_id == envelope["tenant_id"]).with_for_update()
    )
    if sub is None:
        return "unknown"
    event_type = envelope["type"]
    if event_type == "payment.succeeded":
        period_end = _dt(payload.get("billing_period_end"))
        if period_end and (sub.current_period_end is None or period_end > sub.current_period_end):
            sub.current_period_end = period_end
        if sub.status in {"incomplete", "past_due"}:
            await _status(db, sub, "active")
        if payload.get("billing_reason") == "subscription_cycle":
            plan = await db.get(Plan, (sub.tenant_id, sub.plan_id))
            sub.credits_remaining = plan.credits if plan else sub.credits_remaining
            await publish(
                db,
                "subscription.renewed",
                sub.tenant_id,
                {"subscription_id": sub.id, "user_id": sub.user_id, "plan_id": sub.plan_id, "price": money(sub.price_minor, sub.currency),
                 "renewed_at": payload.get("captured_at") or datetime.now(UTC).isoformat(),
                 "period_end": (sub.current_period_end or datetime.now(UTC)).isoformat()},
            )
    elif event_type == "payment.failed":
        if sub.status == "active":
            await _status(db, sub, "past_due")
    elif event_type == "payment.billing_agreement_updated":
        status = payload["status"]
        if payload.get("current_period_end"):
            sub.current_period_end = _dt(payload["current_period_end"])
        if sub.status in {"cancelled", "expired"}:
            return "no_change"
        sub.cancel_at_period_end = bool(payload.get("cancel_at_period_end")) or sub.cancel_at_period_end
        if status == "canceled":
            was_active = sub.status in {"active", "past_due"}
            await _status(db, sub, "cancelled")
            if was_active:
                await publish(
                    db,
                    "subscription.churned",
                    sub.tenant_id,
                    {"subscription_id": sub.id, "user_id": sub.user_id, "plan_id": sub.plan_id,
                     "reason": "voluntary" if sub.cancel_at_period_end else "payment_failure",
                     "lost_mrr": money(_monthly(sub.price_minor, sub.billing_cycle), sub.currency), "churned_at": datetime.now(UTC).isoformat()},
                )
        elif status == "incomplete_expired":
            await _status(db, sub, "expired")
        elif status in {"past_due", "unpaid"} and sub.status == "active":
            await _status(db, sub, "past_due")
        elif status == "paused":
            await _status(db, sub, "paused")
        elif status == "active" and sub.status in {"past_due", "paused"}:
            await _status(db, sub, "active")
    return "applied"
