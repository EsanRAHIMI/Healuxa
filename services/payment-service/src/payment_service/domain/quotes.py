"""Server-side pricing. Clients name *what* they pay for; amounts always come from here."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from healuxa_py_common.middleware.auth import Principal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from payment_service.config import settings
from payment_service.domain.access import conflict, forbidden, is_manager, not_found, unprocessable
from payment_service.domain.money import Line, apply_bps, make_line, totals
from payment_service.infra.catalog import CatalogUnavailable, get_catalog
from payment_service.infra.models import AppointmentView, MembershipView, Quote

# Generic descriptions on purpose: payment records and invoices carry no service names (health data).
DESCRIPTIONS = {
    "professional_fee": "Professional fee",
    "facility_fee": "Facility fee",
    "membership_fee": "Healuxa membership",
}
LINE_CATEGORIES = {"professional_fee": "professional_service", "facility_fee": "facility_service", "platform_fee": "platform_fee"}
CYCLE_LABEL = {"monthly": "monthly", "quarterly": "quarterly", "annual": "annual"}


def tax_status() -> str:
    return "reviewed" if settings.tax_config_reviewed else "pending_accountant_review"


def platform_fee_label() -> str:
    pct = settings.platform_fee_bps / 100
    label = f"{settings.platform_fee_label} ({pct:g}%"
    if settings.platform_fee_fixed_minor:
        label += f" + {settings.currency} {settings.platform_fee_fixed_minor / 100:.2f}"
    return label + ")"


def _line(code: str, net: int, payee_type: str, payee_id: str | None, *, category: str | None = None, description: str | None = None) -> Line:
    category = category or LINE_CATEGORIES[code]
    try:
        return make_line(
            code=code,
            description=description or DESCRIPTIONS.get(code, code),
            category=category,
            net_minor=net,
            vat_rates_bps=settings.vat_rates_bps,
            payee_type=payee_type,
            payee_id=payee_id,
        )
    except KeyError:
        raise unprocessable(f"Unknown tax category: {category}", "lines.category") from None


def platform_fee_line(base_minor: int) -> Line | None:
    fee = apply_bps(base_minor, settings.platform_fee_bps) + settings.platform_fee_fixed_minor
    if fee <= 0:
        return None
    return _line("platform_fee", fee, "healuxa", None, description=platform_fee_label())


def appointment_lines(professional_minor: int, facility_minor: int, provider_id: str, facility_id: str | None) -> list[Line]:
    lines = []
    if professional_minor:
        lines.append(_line("professional_fee", professional_minor, "provider", provider_id))
    if facility_minor:
        lines.append(_line("facility_fee", facility_minor, "facility" if facility_id else "provider", facility_id or provider_id))
    fee = platform_fee_line(professional_minor + facility_minor)
    if fee:
        lines.append(fee)
    return lines


def membership_lines(price_minor: int, plan_id: str, billing_cycle: str) -> list[Line]:
    return [
        _line(
            "membership_fee",
            price_minor,
            "healuxa",
            None,
            category="membership",
            description=f"{DESCRIPTIONS['membership_fee']} ({plan_id}, {CYCLE_LABEL.get(billing_cycle, billing_cycle)})",
        )
    ]


async def _appointment_quote(db: AsyncSession, principal: Principal, subject_id: str) -> dict[str, Any]:
    appointment = await db.get(AppointmentView, subject_id)
    if appointment is None or appointment.tenant_id != principal.tenant_id or appointment.user_id != principal.user_id:
        raise not_found("Appointment")
    if appointment.status in {"declined", "completed", "no_show", "cancelled"}:
        raise conflict(f"Appointment is {appointment.status}")
    try:
        offering = await get_catalog().get_offering(appointment.service_id)
    except CatalogUnavailable:
        raise unprocessable("Catalog temporarily unavailable; retry") from None
    if offering is None or offering.status != "active":
        raise unprocessable("Service offering is not bookable", "subject_id")
    if offering.provider_id != appointment.provider_id:
        raise unprocessable("Offering does not belong to the appointment's provider", "subject_id")
    if offering.price_type != "fixed" or offering.professional_fee_minor is None:
        raise unprocessable("Offering has no fixed price; a staff quote is required", "subject_id")
    if offering.currency != settings.currency:
        raise unprocessable(f"Only {settings.currency} is supported", "currency")
    lines = appointment_lines(offering.professional_fee_minor, offering.facility_fee_minor or 0, offering.provider_id, offering.facility_id)
    return {
        "user_id": principal.user_id,
        "lines": lines,
        "provider_id": offering.provider_id,
        "facility_id": offering.facility_id,
        "service_id": offering.id,
    }


async def _membership_quote(db: AsyncSession, principal: Principal, subject_id: str) -> dict[str, Any]:
    if not settings.membership_payments_enabled:
        raise not_found("Membership payments")
    membership = await db.get(MembershipView, subject_id)
    if membership is None or membership.tenant_id != principal.tenant_id or membership.user_id != principal.user_id:
        raise not_found("Subscription")
    if membership.processor_subscription_id:
        raise conflict("Membership already has a billing agreement")
    return {"user_id": principal.user_id, "lines": membership_lines(membership.price_minor, membership.plan_id, membership.billing_cycle)}


def _concierge_quote(principal: Principal, user_id: str | None, raw_lines: list[dict] | None) -> dict[str, Any]:
    if not is_manager(principal):
        raise forbidden("Concierge quotes are prepared by payments staff")
    if not user_id:
        raise unprocessable("user_id is required for concierge quotes", "user_id")
    if not raw_lines:
        raise unprocessable("At least one line is required", "lines")
    lines = []
    for raw in raw_lines:
        payee_type = raw.get("payee_type") or "healuxa"
        if payee_type != "healuxa" and not raw.get("payee_id"):
            raise unprocessable("payee_id is required for provider/facility lines", "lines.payee_id")
        lines.append(
            _line(
                raw["code"],
                int(raw["net_minor"]),
                payee_type,
                raw.get("payee_id") if payee_type != "healuxa" else None,
                category=raw["category"],
                description=raw["description"],
            )
        )
    return {"user_id": user_id, "lines": lines}


async def create_quote(db: AsyncSession, principal: Principal, body: dict[str, Any]) -> Quote:
    subject_type = body["subject_type"]
    subject_id = body["subject_id"]
    if subject_type != "concierge_case" and body.get("lines"):
        raise unprocessable("lines are only accepted for concierge quotes; prices are computed server-side", "lines")
    if subject_type == "appointment":
        priced = await _appointment_quote(db, principal, subject_id)
    elif subject_type == "membership":
        priced = await _membership_quote(db, principal, subject_id)
    else:
        priced = _concierge_quote(principal, body.get("user_id"), body.get("lines"))
    lines: list[Line] = priced["lines"]
    subtotal, tax, total = totals(lines)
    if total <= 0:
        raise unprocessable("Quote total must be positive")
    now = datetime.now(UTC)
    quote = Quote(
        id=str(ULID()),
        tenant_id=principal.tenant_id,
        user_id=priced["user_id"],
        subject_type=subject_type,
        subject_id=subject_id,
        provider_id=priced.get("provider_id"),
        facility_id=priced.get("facility_id"),
        service_id=priced.get("service_id"),
        currency=settings.currency,
        lines=[line.as_dict() for line in lines],
        subtotal_minor=subtotal,
        tax_minor=tax,
        total_minor=total,
        tax_status=tax_status(),
        created_by=principal.user_id,
        expires_at=now + timedelta(seconds=settings.quote_ttl_seconds),
        created_at=now,
    )
    db.add(quote)
    await db.flush()
    return quote


async def get_quote_for(db: AsyncSession, principal: Principal, quote_id: str) -> Quote:
    quote = await db.scalar(select(Quote).where(Quote.id == quote_id, Quote.tenant_id == principal.tenant_id))
    if quote is None or (quote.user_id != principal.user_id and not is_manager(principal)):
        raise not_found("Quote")
    return quote


def quote_view(quote: Quote, *, used: bool = False) -> dict[str, Any]:
    m = lambda v: {"amount_minor": v, "currency": quote.currency}  # noqa: E731
    status = "used" if used else ("expired" if quote.expires_at <= datetime.now(UTC) else "open")
    return {
        "id": quote.id,
        "user_id": quote.user_id,
        "subject_type": quote.subject_type,
        "subject_id": quote.subject_id,
        "provider_id": quote.provider_id,
        "facility_id": quote.facility_id,
        "service_id": quote.service_id,
        "currency": quote.currency,
        "lines": quote.lines,
        "subtotal": m(quote.subtotal_minor),
        "tax": m(quote.tax_minor),
        "total": m(quote.total_minor),
        "tax_status": quote.tax_status,
        "status": status,
        "expires_at": quote.expires_at.isoformat(),
        "created_at": quote.created_at.isoformat(),
    }
