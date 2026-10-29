"""Booking engine: holds, requests, confirmation, cancellation, check-in, completion, no-show, reschedule.

State machine (see docs/ARCHITECTURE.md "Booking")::

    held ──submit──► requested ──accept──► confirmed ──check_in──► checked_in ──complete──► completed
      │                 │  └──decline──► declined      │  └──complete──► completed
      │                 │                              ├──no_show──► no_show
      ├─(TTL)─► expired ├─(start passed)─► expired      │
      └─cancel─► cancelled  └─cancel─► cancelled       └─cancel─► cancelled
    requested|confirmed ──reschedule──► rescheduled  (+ a new linked appointment)

``confirmed`` is reachable only through ``accept`` by the provider owner, a facility
``facility_admin``/``scheduler`` or ``appointments:manage`` — or a reschedule made by one of them.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

from healuxa_py_common.errors import ApiError
from healuxa_py_common.middleware.auth import Principal
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from appointment_service.clients.provider_directory import ProviderDirectory, SchedulingContext
from appointment_service.config import settings
from appointment_service.domain import schemas
from appointment_service.domain.access import Access, access_for, is_manager, load_access
from appointment_service.domain.availability import context_for_start, require_free_slot
from appointment_service.domain.clock import clock
from appointment_service.domain.errors import conflict, forbidden, idempotency_conflict, not_found, unprocessable
from appointment_service.domain.lifecycle import (
    cancel_reminders,
    change_status,
    expire_if_due,
    expire_stale_holds,
    present,
    present_one,
    record,
    schedule_reminders,
)
from appointment_service.domain.pagination import decode_cursor, encode_cursor
from appointment_service.events.publisher import event_publisher, ts
from appointment_service.infra.models import (
    CUSTOMER_OVERLAP_CONSTRAINT,
    IDEMPOTENCY_INDEX,
    PROVIDER_OVERLAP_CONSTRAINT,
    TRANSITION_IDEMPOTENCY_INDEX,
    Appointment,
    AppointmentTransition,
)

PAID_STATUSES = ("not_required", "authorized", "captured")


def _request_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _is_deadlock(exc: DBAPIError) -> bool:
    # Concurrent inserts racing for one exclusion-constraint range can deadlock; PostgreSQL aborts one
    # of them. The victim lost the race for an overlapping slot, so it is a conflict like any other.
    cause = getattr(exc.orig, "__cause__", None)
    return getattr(exc.orig, "sqlstate", None) == "40P01" or getattr(cause, "sqlstate", None) == "40P01"


def _slot_conflict(exc: DBAPIError) -> Exception:
    if not isinstance(exc, IntegrityError) and not _is_deadlock(exc):
        return exc
    if _is_deadlock(exc):
        return conflict("This slot is no longer available")
    message = str(exc.orig) if exc.orig is not None else str(exc)
    if CUSTOMER_OVERLAP_CONSTRAINT in message:
        return conflict("The customer already has an appointment overlapping this time")
    if PROVIDER_OVERLAP_CONSTRAINT in message:
        return conflict("This slot is no longer available")
    return conflict("The appointment conflicts with existing data")


def _new_appointment(
    context: SchedulingContext,
    *,
    tenant_id: str,
    user_id: str,
    start: datetime,
    end: datetime,
    occupied_until: datetime,
    now: datetime,
    status: str,
    milestone_id: str | None,
    channel: str | None,
    payment_status: str,
) -> Appointment:
    offering = context.offering
    return Appointment(
        id=str(ULID()),
        tenant_id=tenant_id,
        user_id=user_id,
        provider_id=offering.provider_id,
        facility_id=offering.facility_id,
        branch_id=offering.branch_id,
        service_id=offering.id,
        milestone_id=milestone_id,
        status=status,
        starts_at=start,
        ends_at=end,
        blocked_until=occupied_until,
        timezone=context.branch.timezone,
        duration_minutes=offering.duration_minutes,
        buffer_minutes=offering.buffer_minutes,
        service_name=offering.name,
        price_minor=offering.price_minor,
        currency=offering.currency if offering.price_minor is not None else None,
        payment_status=payment_status,
        channel=channel,
        version=1,
        created_at=now,
        updated_at=now,
    )


def _initial_payment_status(context: SchedulingContext) -> str:
    if settings.payment_required and (context.offering.price_minor or 0) > 0:
        return "pending"
    return "not_required"


class BookingService:
    # ── holds ─────────────────────────────────────────────────────────────────────────────────────
    async def create_hold(
        self,
        db: AsyncSession,
        directory: ProviderDirectory,
        principal: Principal,
        body: schemas.CreateAppointment,
        *,
        idempotency_key: str | None,
    ) -> schemas.Appointment:
        customer = body.user_id or principal.user_id
        if customer != principal.user_id and not is_manager(principal):
            raise forbidden("Only appointments:manage may book on behalf of another customer")
        start = body.scheduled_at.astimezone(UTC)
        request_hash = _request_hash(
            {
                "service_id": body.service_id,
                "scheduled_at": start.isoformat(),
                "milestone_id": body.milestone_id,
                "channel": body.channel,
                "user_id": customer,
            }
        )
        if idempotency_key:
            # Serialise concurrent retries of one key (held until commit/rollback), then replay if done.
            await db.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"),
                {"k": f"appointment-create:{principal.tenant_id}:{customer}:{idempotency_key}"},
            )
            replay = await self._idempotent_replay(db, principal.tenant_id, customer, idempotency_key, request_hash)
            if replay is not None:
                await db.commit()
                return replay

        context = await context_for_start(directory, principal.tenant_id, body.service_id, start)
        if context.provider.user_id == customer:
            raise unprocessable("Providers cannot book their own offerings", "service_id")

        now = clock.now()
        await expire_stale_holds(db, now, provider_id=context.offering.provider_id, user_id=customer)
        active_holds = await db.scalar(
            select(func.count())
            .select_from(Appointment)
            .where(
                Appointment.tenant_id == principal.tenant_id,
                Appointment.user_id == customer,
                Appointment.status == "held",
                Appointment.expires_at > now,
            )
        )
        if (active_holds or 0) >= settings.max_active_holds_per_customer:
            raise conflict(f"At most {settings.max_active_holds_per_customer} active holds per customer")

        slot = await require_free_slot(db, context, start)
        appointment = _new_appointment(
            context,
            tenant_id=principal.tenant_id,
            user_id=customer,
            start=slot.start,
            end=slot.end,
            occupied_until=slot.occupied_until,
            now=now,
            status="held",
            milestone_id=body.milestone_id,
            channel=body.channel,
            payment_status=_initial_payment_status(context),
        )
        appointment.expires_at = now + timedelta(minutes=settings.hold_ttl_minutes)
        appointment.idempotency_key = idempotency_key
        appointment.request_hash = request_hash
        db.add(appointment)
        record(
            db,
            appointment,
            action="hold",
            from_status=None,
            to_status="held",
            actor_type="customer" if customer == principal.user_id else "platform",
            actor_id=principal.user_id,
            at=now,
        )
        try:
            await db.flush()
        except DBAPIError as exc:
            await db.rollback()
            if idempotency_key and IDEMPOTENCY_INDEX in str(exc.orig):
                replay = await self._idempotent_replay(db, principal.tenant_id, customer, idempotency_key, request_hash)
                if replay is not None:
                    return replay
            raise _slot_conflict(exc) from exc
        await db.commit()
        return await present_one(db, appointment)

    async def _idempotent_replay(
        self, db: AsyncSession, tenant_id: str, user_id: str, key: str, request_hash: str
    ) -> schemas.Appointment | None:
        existing = await db.scalar(
            select(Appointment).where(
                Appointment.tenant_id == tenant_id, Appointment.user_id == user_id, Appointment.idempotency_key == key
            )
        )
        if existing is None:
            return None
        if existing.request_hash != request_hash:
            raise idempotency_conflict()
        return await present_one(db, existing)

    # ── reads ─────────────────────────────────────────────────────────────────────────────────────
    async def _load(self, db: AsyncSession, tenant_id: str, appointment_id: str, *, for_update: bool = False) -> Appointment:
        stmt = select(Appointment).where(Appointment.id == appointment_id, Appointment.tenant_id == tenant_id)
        if for_update:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        appointment = await db.scalar(stmt)
        if appointment is None:
            raise not_found("Appointment")
        return appointment

    async def _visible(
        self, db: AsyncSession, directory: ProviderDirectory, principal: Principal, appointment_id: str, *, for_update: bool = False
    ) -> tuple[Appointment, Access]:
        appointment = await self._load(db, principal.tenant_id, appointment_id, for_update=for_update)
        access = await access_for(directory, principal, appointment)
        if not access.can_view(appointment):
            # Indistinguishable from a missing appointment: no existence oracle across customers.
            raise not_found("Appointment")
        return appointment, access

    async def get(
        self, db: AsyncSession, directory: ProviderDirectory, principal: Principal, appointment_id: str
    ) -> schemas.Appointment:
        appointment, _ = await self._visible(db, directory, principal, appointment_id)
        now = clock.now()
        if appointment.expires_at is not None and appointment.expires_at <= now and appointment.status in ("held", "requested"):
            appointment = await self._load(db, principal.tenant_id, appointment_id, for_update=True)
            if await expire_if_due(db, appointment, now):
                await db.commit()
        return await present_one(db, appointment)

    async def history(
        self, db: AsyncSession, directory: ProviderDirectory, principal: Principal, appointment_id: str
    ) -> list[schemas.StatusTransition]:
        appointment, _ = await self._visible(db, directory, principal, appointment_id)
        rows = await db.scalars(
            select(AppointmentTransition)
            .where(AppointmentTransition.appointment_id == appointment.id)
            .order_by(AppointmentTransition.occurred_at, AppointmentTransition.id)
        )
        return [
            schemas.StatusTransition(
                id=t.id,
                appointment_id=t.appointment_id,
                from_status=t.from_status,
                to_status=t.to_status,
                actor_type=t.actor_type,
                actor_id=t.actor_id,
                reason_code=t.reason_code,
                reason=t.reason,
                occurred_at=t.occurred_at,
            )
            for t in rows
        ]

    async def list(
        self,
        db: AsyncSession,
        directory: ProviderDirectory,
        principal: Principal,
        *,
        user_id: str | None,
        provider_id: str | None,
        branch_id: str | None,
        facility_id: str | None,
        status: str | None,
        from_: datetime | None,
        to: datetime | None,
        limit: int,
        cursor: str | None,
        sort: str,
    ) -> tuple[list[schemas.Appointment], str | None, bool]:
        for name, value in (("from", from_), ("to", to)):
            if value is not None and value.tzinfo is None:
                raise unprocessable(f"{name} must include a UTC offset", name)
        now = clock.now()
        if await expire_stale_holds(db, now, tenant_id=principal.tenant_id):
            await db.commit()

        stmt = select(Appointment).where(Appointment.tenant_id == principal.tenant_id)
        if provider_id or branch_id or facility_id:
            access = await load_access(directory, principal)
            if not access.has_staff_scope:
                raise forbidden("Calendar views need a provider or facility scheduling role")
            if not access.is_manager:
                stmt = stmt.where(
                    or_(
                        Appointment.provider_id.in_(access.provider_ids),
                        Appointment.facility_id.in_(access.scheduling_facilities),
                    )
                )
            if provider_id:
                stmt = stmt.where(Appointment.provider_id == provider_id)
            if branch_id:
                stmt = stmt.where(Appointment.branch_id == branch_id)
            if facility_id:
                stmt = stmt.where(Appointment.facility_id == facility_id)
            if user_id:
                stmt = stmt.where(Appointment.user_id == user_id)
        else:
            if user_id and user_id != principal.user_id and not is_manager(principal):
                raise forbidden("Customers can only list their own appointments")
            if user_id or not is_manager(principal):
                stmt = stmt.where(Appointment.user_id == (user_id or principal.user_id))
        if status:
            stmt = stmt.where(Appointment.status == status)
        if from_ is not None:
            stmt = stmt.where(Appointment.starts_at >= from_)
        if to is not None:
            stmt = stmt.where(Appointment.starts_at < to)

        descending = sort == "-scheduled_at"
        if cursor:
            after_start, after_id = decode_cursor(cursor, sort)
            if descending:
                stmt = stmt.where(
                    or_(Appointment.starts_at < after_start, and_(Appointment.starts_at == after_start, Appointment.id < after_id))
                )
            else:
                stmt = stmt.where(
                    or_(Appointment.starts_at > after_start, and_(Appointment.starts_at == after_start, Appointment.id > after_id))
                )
        order = (Appointment.starts_at.desc(), Appointment.id.desc()) if descending else (Appointment.starts_at, Appointment.id)
        rows = list((await db.scalars(stmt.order_by(*order).limit(limit + 1))).all())
        has_more = len(rows) > limit
        rows = rows[:limit]
        next_cursor = encode_cursor(rows[-1].starts_at, rows[-1].id, sort) if has_more else None
        return await present(db, rows), next_cursor, has_more

    # ── transitions ───────────────────────────────────────────────────────────────────────────────
    async def _prepare(
        self,
        db: AsyncSession,
        directory: ProviderDirectory,
        principal: Principal,
        appointment_id: str,
        *,
        action: str,
        if_match: str | None,
        idempotency_key: str | None,
    ) -> tuple[Appointment, Access, AppointmentTransition | None]:
        """Lock, authorise visibility, apply lazy expiry, handle idempotent replays and If-Match."""
        appointment, access = await self._visible(db, directory, principal, appointment_id, for_update=True)
        if idempotency_key:
            previous = await db.scalar(
                select(AppointmentTransition).where(
                    AppointmentTransition.appointment_id == appointment.id,
                    AppointmentTransition.idempotency_key == idempotency_key,
                )
            )
            if previous is not None:
                if previous.action != action:
                    raise idempotency_conflict()
                return appointment, access, previous
        now = clock.now()
        if await expire_if_due(db, appointment, now):
            await db.commit()
            stage = "hold" if appointment.requested_at is None else "request"
            raise conflict(f"Appointment has expired (the {stage} deadline passed)")
        if if_match is not None and if_match.strip().strip('"') != f"v{appointment.version}":
            raise conflict("If-Match does not match the current appointment version")
        return appointment, access, None

    async def transition(
        self,
        db: AsyncSession,
        directory: ProviderDirectory,
        principal: Principal,
        appointment_id: str,
        body: schemas.TransitionRequest,
        *,
        if_match: str | None,
        idempotency_key: str | None,
    ) -> schemas.Appointment:
        appointment, access, replayed = await self._prepare(
            db, directory, principal, appointment_id, action=body.transition, if_match=if_match, idempotency_key=idempotency_key
        )
        if replayed is not None:
            return await present_one(db, appointment)
        handler = getattr(self, f"_do_{body.transition}")
        await handler(db, directory, appointment, access, body, idempotency_key)
        await db.commit()
        return await present_one(db, appointment)

    def _invalid(self, appointment: Appointment, action: str) -> Exception:
        return conflict(f"Cannot {action.replace('_', '-')} an appointment that is {appointment.status}")

    def _require_staff(self, appointment: Appointment, access: Access) -> str:
        party = access.staff_party(appointment)
        if party is None:
            raise forbidden("Only the provider, the facility's schedulers or platform staff may do this")
        return party

    async def _do_submit(self, db, directory, appointment: Appointment, access: Access, body, key) -> None:
        if not (access.is_customer(appointment) or access.is_manager):
            raise forbidden("Only the customer may submit a booking request")
        if appointment.status != "held":
            raise self._invalid(appointment, "submit")
        now = clock.now()
        previous = change_status(appointment, "requested", now)
        appointment.requested_at = now
        appointment.expires_at = appointment.starts_at  # unanswered requests expire at the start time
        party = "customer" if access.is_customer(appointment) else "platform"
        record(db, appointment, action="submit", from_status=previous, to_status="requested", actor_type=party, actor_id=access.principal.user_id, at=now, reason=body.reason, idempotency_key=key)
        await event_publisher.publish(db=db, event_type="appointment.requested", appointment=appointment, extra={"requested_at": ts(now)}, actor=access.actor())

    async def _do_accept(self, db, directory: ProviderDirectory, appointment: Appointment, access: Access, body, key) -> None:
        party = self._require_staff(appointment, access)
        if appointment.status != "requested":
            raise self._invalid(appointment, "accept")
        if appointment.payment_status not in PAID_STATUSES:
            raise conflict("Payment has not been authorized for this appointment")
        # The practice must still be bookable at confirmation time (provider/facility not suspended).
        try:
            await context_for_start(directory, appointment.tenant_id, appointment.service_id, appointment.starts_at)
        except ApiError as exc:
            if exc.status == 404:
                raise conflict("The service offering is no longer bookable; decline or cancel instead") from exc
            raise
        now = clock.now()
        previous = change_status(appointment, "confirmed", now)
        appointment.confirmed_at = now
        appointment.expires_at = None
        record(db, appointment, action="accept", from_status=previous, to_status="confirmed", actor_type=party, actor_id=access.principal.user_id, at=now, reason=body.reason, idempotency_key=key)
        schedule_reminders(db, appointment, now)
        response_seconds = max(int((now - (appointment.requested_at or now)).total_seconds()), 0)
        await event_publisher.publish(db=db, event_type="appointment.accepted", appointment=appointment, extra={"response_seconds": response_seconds}, actor=access.actor())
        await event_publisher.publish(db=db, event_type="appointment.created", appointment=appointment, extra={"channel": _event_channel(appointment)}, actor=access.actor())

    async def _do_decline(self, db, directory, appointment: Appointment, access: Access, body: schemas.TransitionRequest, key) -> None:
        party = self._require_staff(appointment, access)
        if appointment.status != "requested":
            raise self._invalid(appointment, "decline")
        reason_code = body.reason_code or "other"
        if reason_code not in schemas.DECLINE_REASONS:
            raise unprocessable("reason_code must be one of " + ", ".join(schemas.DECLINE_REASONS), "reason_code")
        now = clock.now()
        previous = change_status(appointment, "declined", now)
        appointment.decline_reason = reason_code
        appointment.expires_at = None
        record(db, appointment, action="decline", from_status=previous, to_status="declined", actor_type=party, actor_id=access.principal.user_id, at=now, reason_code=reason_code, reason=body.reason, idempotency_key=key)
        response_seconds = max(int((now - (appointment.requested_at or now)).total_seconds()), 0)
        await event_publisher.publish(db=db, event_type="appointment.declined", appointment=appointment, extra={"reason": reason_code, "response_seconds": response_seconds}, actor=access.actor())

    async def _do_cancel(self, db, directory, appointment: Appointment, access: Access, body: schemas.TransitionRequest, key) -> None:
        if appointment.status not in ("held", "requested", "confirmed"):
            raise self._invalid(appointment, "cancel")
        now = clock.now()
        if access.is_customer(appointment):
            party = "customer"
            if appointment.status == "confirmed" and now > appointment.starts_at - timedelta(minutes=settings.customer_cancel_cutoff_minutes):
                raise conflict(f"Confirmed appointments can be cancelled by the customer until {settings.customer_cancel_cutoff_minutes} minutes before the start")
        else:
            party = self._require_staff(appointment, access)
            if appointment.status == "held":
                raise forbidden("A hold can only be released by the customer")
            if party != "platform" and now >= appointment.starts_at:
                raise conflict("The appointment has started; mark it completed or no-show instead")
        reason_code = body.reason_code or ("customer_request" if party == "customer" else "other")
        if reason_code not in schemas.CANCEL_REASONS:
            raise unprocessable("reason_code must be one of " + ", ".join(schemas.CANCEL_REASONS), "reason_code")
        previous = change_status(appointment, "cancelled", now)
        appointment.cancelled_at = now
        appointment.cancelled_by = party
        appointment.expires_at = None
        record(db, appointment, action="cancel", from_status=previous, to_status="cancelled", actor_type=party, actor_id=access.principal.user_id, at=now, reason_code=reason_code, reason=body.reason, idempotency_key=key)
        await cancel_reminders(db, appointment.id)
        if previous != "held":  # holds are private to the customer and never announced
            await event_publisher.publish(
                db=db,
                event_type="appointment.cancelled",
                appointment=appointment,
                extra={"cancelled_at": ts(now), "party": party, "reason": reason_code, "previous_status": previous},
                actor=access.actor(),
            )

    async def _do_check_in(self, db, directory, appointment: Appointment, access: Access, body, key) -> None:
        party = self._require_staff(appointment, access)
        if appointment.status != "confirmed":
            raise self._invalid(appointment, "check_in")
        now = clock.now()
        opens = appointment.starts_at - timedelta(minutes=settings.check_in_opens_minutes)
        if now < opens or now >= appointment.ends_at:
            raise conflict(f"Check-in is possible from {settings.check_in_opens_minutes} minutes before the start until the end")
        previous = change_status(appointment, "checked_in", now)
        appointment.checked_in_at = now
        record(db, appointment, action="check_in", from_status=previous, to_status="checked_in", actor_type=party, actor_id=access.principal.user_id, at=now, reason=body.reason, idempotency_key=key)

    async def _do_complete(self, db, directory, appointment: Appointment, access: Access, body, key) -> None:
        party = self._require_staff(appointment, access)
        if appointment.status not in ("confirmed", "checked_in"):
            raise self._invalid(appointment, "complete")
        now = clock.now()
        if now < appointment.starts_at:
            raise conflict("An appointment cannot be completed before it starts")
        previous = change_status(appointment, "completed", now)
        appointment.completed_at = now
        record(db, appointment, action="complete", from_status=previous, to_status="completed", actor_type=party, actor_id=access.principal.user_id, at=now, reason=body.reason, idempotency_key=key)
        await cancel_reminders(db, appointment.id)
        extra: dict = {"completed_at": ts(now), "duration_minutes": appointment.duration_minutes}
        if appointment.price_minor is not None and appointment.currency:
            extra["amount"] = {"amount_minor": appointment.price_minor, "currency": appointment.currency}
        await event_publisher.publish(db=db, event_type="appointment.completed", appointment=appointment, extra=extra, actor=access.actor())

    async def _do_no_show(self, db, directory, appointment: Appointment, access: Access, body: schemas.TransitionRequest, key) -> None:
        party = self._require_staff(appointment, access)
        no_show_party = body.party or "customer"
        if no_show_party == "provider" and not access.is_manager:
            raise forbidden("Only platform staff may record a provider no-show")
        if appointment.status != "confirmed":
            raise self._invalid(appointment, "no_show")
        now = clock.now()
        if now < appointment.starts_at + timedelta(minutes=settings.no_show_grace_minutes):
            raise conflict(f"A no-show can be recorded {settings.no_show_grace_minutes} minutes after the start")
        previous = change_status(appointment, "no_show", now)
        appointment.no_show_party = no_show_party
        record(db, appointment, action="no_show", from_status=previous, to_status="no_show", actor_type=party, actor_id=access.principal.user_id, at=now, reason_code=no_show_party, reason=body.reason, idempotency_key=key)
        await cancel_reminders(db, appointment.id)
        await event_publisher.publish(db=db, event_type="appointment.no_show", appointment=appointment, extra={"party": no_show_party}, actor=access.actor())

    # ── reschedule ────────────────────────────────────────────────────────────────────────────────
    async def reschedule(
        self,
        db: AsyncSession,
        directory: ProviderDirectory,
        principal: Principal,
        appointment_id: str,
        body: schemas.RescheduleRequest,
        *,
        if_match: str | None,
        idempotency_key: str | None,
    ) -> schemas.Appointment:
        old, access, replayed = await self._prepare(
            db, directory, principal, appointment_id, action="reschedule", if_match=if_match, idempotency_key=idempotency_key
        )
        if replayed is not None and old.rescheduled_to_id:
            return await present_one(db, await self._load(db, principal.tenant_id, old.rescheduled_to_id))
        if old.status not in ("requested", "confirmed"):
            raise self._invalid(old, "reschedule")
        now = clock.now()
        if access.is_customer(old):
            party = "customer"
            if now > old.starts_at - timedelta(minutes=settings.customer_cancel_cutoff_minutes):
                raise conflict(f"Customers can reschedule until {settings.customer_cancel_cutoff_minutes} minutes before the start")
        else:
            party = self._require_staff(old, access)
            if now >= old.starts_at:
                raise conflict("The appointment has already started")

        start = body.scheduled_at.astimezone(UTC)
        context = await context_for_start(directory, old.tenant_id, old.service_id, start)
        slot = await require_free_slot(db, context, start, exclude_id=old.id)
        new_status = "confirmed" if party != "customer" and old.status == "confirmed" else "requested"
        if party != "customer" and old.status == "requested":
            new_status = "confirmed"  # the confirming side proposed the new time itself

        new = _new_appointment(
            context,
            tenant_id=old.tenant_id,
            user_id=old.user_id,
            start=slot.start,
            end=slot.end,
            occupied_until=slot.occupied_until,
            now=now,
            status=new_status,
            milestone_id=old.milestone_id,
            channel=old.channel,
            payment_status=old.payment_status,
        )
        new.rescheduled_from_id = old.id
        new.requested_at = old.requested_at or now
        if new_status == "confirmed":
            new.confirmed_at = now
        else:
            new.requested_at = now
            new.expires_at = new.starts_at

        # Close the original first so its slot stops blocking (same transaction), then claim the new one.
        previous = change_status(old, "rescheduled", now)
        old.expires_at = None
        record(db, old, action="reschedule", from_status=previous, to_status="rescheduled", actor_type=party, actor_id=principal.user_id, at=now, reason=body.reason, idempotency_key=idempotency_key)
        await cancel_reminders(db, old.id)
        try:
            await db.flush()
            db.add(new)
            await db.flush()
            old.rescheduled_to_id = new.id
            record(db, new, action="reschedule", from_status=None, to_status=new_status, actor_type=party, actor_id=principal.user_id, at=now, reason_code="rescheduled")
            if new_status == "confirmed":
                schedule_reminders(db, new, now)
            await db.flush()
        except DBAPIError as exc:
            await db.rollback()
            if idempotency_key and TRANSITION_IDEMPOTENCY_INDEX in str(exc.orig):
                raise conflict("A concurrent request with this Idempotency-Key is in progress") from exc
            raise _slot_conflict(exc) from exc

        actor = access.actor()
        await event_publisher.publish(
            db=db,
            event_type="appointment.rescheduled",
            appointment=new,
            extra={"previous_appointment_id": old.id, "previous_scheduled_at": ts(old.starts_at), "party": party, "status": new_status},
            actor=actor,
        )
        if new_status == "confirmed":
            await event_publisher.publish(db=db, event_type="appointment.created", appointment=new, extra={"channel": _event_channel(new)}, actor=actor)
        else:
            await event_publisher.publish(db=db, event_type="appointment.requested", appointment=new, extra={"requested_at": ts(now)}, actor=actor)
        await db.commit()
        return await present_one(db, new)


def _event_channel(appointment: Appointment) -> str:
    # Event channel vocabulary (common.schema.json Channel); concierge bookings are made in-app by staff.
    return {"app": "app", "web": "web", "whatsapp": "whatsapp"}.get(appointment.channel or "", "in_app")


booking_service = BookingService()
