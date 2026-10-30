from __future__ import annotations

from datetime import UTC, datetime, time
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Response
from healuxa_py_common.errors import ApiError
from healuxa_py_common.middleware.auth import Principal
from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from notification_service.api.deps import get_db, require_permission
from notification_service.domain import preferences as prefs
from notification_service.domain.notify import Recipient, notify
from notification_service.domain.pagination import decode_cursor, encode_cursor
from notification_service.domain.schemas import (
    Category,
    DeliveryStatus,
    DeviceTokenCreate,
    DeviceTokenOut,
    MarkedCount,
    NotificationOut,
    NotificationPage,
    PageMeta,
    PreferencesOut,
    PreferencesUpdate,
    QuietHours,
    RecipientLinkIn,
    SendRequest,
    SendResult,
    UnreadCount,
)
from notification_service.domain.templates import TemplateError
from notification_service.infra.models import DeviceToken, Notification, Preference, RecipientLink

router = APIRouter(prefix="/v1", tags=["notifications"])

Db = Annotated[AsyncSession, Depends(get_db)]
Reader = Annotated[Principal, Depends(require_permission("notifications:read"))]
Writer = Annotated[Principal, Depends(require_permission("notifications:write"))]
Service = Annotated[Principal, Depends(require_permission("service"))]
Limit = Annotated[int, Query(ge=1, le=100)]


def _not_found(what: str) -> ApiError:
    return ApiError(status=404, code="not_found", title="Not found", detail=f"{what} not found")


def _unprocessable(detail: str, field: str) -> ApiError:
    return ApiError(status=422, code="unprocessable", title="Unprocessable", detail=detail, errors=[{"field": field, "code": "invalid", "message": detail}])


def _out(n: Notification) -> NotificationOut:
    return NotificationOut(
        id=n.id,
        category=n.category,  # type: ignore[arg-type]
        template=n.template_key,
        locale=n.locale,  # type: ignore[arg-type]
        title=n.title,
        body=n.body,
        entity_type=n.entity_type,
        entity_id=n.entity_id,
        read_at=n.read_at,
        created_at=n.created_at,
    )


def _inbox(principal: Principal):
    return and_(
        Notification.tenant_id == principal.tenant_id,
        Notification.user_id == principal.user_id,
        Notification.inbox_visible.is_(True),
    )


# ── inbox ────────────────────────────────────────────────────────────────────


@router.get("/notifications", response_model=NotificationPage, operation_id="listNotifications")
async def list_notifications(
    principal: Reader,
    db: Db,
    unread_only: bool = False,
    category: Category | None = None,
    limit: Limit = 20,
    cursor: str | None = None,
) -> NotificationPage:
    n = Notification
    stmt = select(n).where(_inbox(principal))
    if unread_only:
        stmt = stmt.where(n.read_at.is_(None))
    if category:
        stmt = stmt.where(n.category == category)
    if cursor:
        t, i = decode_cursor(cursor)
        stmt = stmt.where(or_(n.created_at < t, and_(n.created_at == t, n.id < i)))
    rows = list(await db.scalars(stmt.order_by(n.created_at.desc(), n.id.desc()).limit(limit + 1)))
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor(created_at=rows[-1].created_at, resource_id=rows[-1].id) if has_more and rows else None
    return NotificationPage(data=[_out(r) for r in rows], page=PageMeta(next_cursor=next_cursor, limit=limit, has_more=has_more))


@router.get("/notifications/unread-count", response_model=UnreadCount, operation_id="getUnreadNotificationCount")
async def unread_count(principal: Reader, db: Db) -> UnreadCount:
    count = await db.scalar(select(func.count()).select_from(Notification).where(_inbox(principal), Notification.read_at.is_(None)))
    return UnreadCount(unread=int(count or 0))


@router.post("/notifications/{id}/read", response_model=NotificationOut, operation_id="markNotificationRead")
async def mark_read(id: str, principal: Writer, db: Db) -> NotificationOut:
    notification = await db.scalar(select(Notification).where(Notification.id == id, _inbox(principal)))
    if notification is None:
        raise _not_found("Notification")
    if notification.read_at is None:
        notification.read_at = datetime.now(UTC)
        await db.commit()
    return _out(notification)


@router.post("/notifications/read-all", response_model=MarkedCount, operation_id="markAllNotificationsRead")
async def mark_all_read(principal: Writer, db: Db) -> MarkedCount:
    result = await db.execute(
        update(Notification).where(_inbox(principal), Notification.read_at.is_(None)).values(read_at=datetime.now(UTC))
    )
    await db.commit()
    return MarkedCount(marked=int(result.rowcount or 0))


# ── internal direct send ─────────────────────────────────────────────────────


@router.post("/notifications/send", status_code=202, response_model=SendResult, operation_id="sendNotification")
async def send_notification(
    body: SendRequest,
    principal: Service,
    db: Db,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> SendResult:
    if idempotency_key is not None and not 8 <= len(idempotency_key) <= 128:
        raise _unprocessable("Idempotency-Key must be 8-128 characters", "Idempotency-Key")
    source_key = f"send:{idempotency_key}" if idempotency_key else f"send:{ULID()}"
    tenant_id = body.tenant_id or principal.tenant_id
    try:
        result = await notify(
            db,
            Recipient(tenant_id=tenant_id, user_id=body.user_id),
            template_key=body.template,
            params=dict(body.data),
            source_key=source_key,
            entity_type=body.entity_type,
            entity_id=body.entity_id,
            channels=body.requested_channels(),
        )
    except TemplateError as exc:
        raise _unprocessable(str(exc), "template") from None
    if not result.created:
        existing = await db.get(Notification, result.notification_id)
        if existing is not None and existing.template_key != body.template:
            raise ApiError(status=409, code="idempotency_conflict", title="Idempotency conflict", detail="Idempotency-Key was already used for a different notification")
    await db.commit()
    return SendResult(
        notification_id=result.notification_id,
        deliveries=[DeliveryStatus(channel=c, status=s, skip_reason=r) for c, s, r in result.deliveries],  # type: ignore[arg-type]
    )


# ── preferences ──────────────────────────────────────────────────────────────


def _hhmm(value: time | None) -> str | None:
    return value.strftime("%H:%M") if value is not None else None


def _prefs_out(p: prefs.EffectivePreferences) -> PreferencesOut:
    quiet = QuietHours(start=_hhmm(p.quiet_start), end=_hhmm(p.quiet_end)) if p.quiet_start and p.quiet_end else None
    return PreferencesOut(
        user_id=p.user_id,
        locale=p.locale,  # type: ignore[arg-type]
        timezone=p.timezone,
        quiet_hours=quiet,
        marketing_opt_in=p.marketing_opt_in,
        channels=p.channels,
        updated_at=p.updated_at,
    )


def _own(principal: Principal, user_id: str) -> None:
    # Preferences are personal: anyone else's look like they do not exist.
    if user_id != principal.user_id:
        raise _not_found("Preferences")


@router.get("/notifications/preferences/{userId}", response_model=PreferencesOut, operation_id="getPreferences")
async def get_preferences(userId: str, principal: Reader, db: Db) -> PreferencesOut:
    _own(principal, userId)
    return _prefs_out(await prefs.load(db, principal.tenant_id, userId))


@router.put("/notifications/preferences/{userId}", response_model=PreferencesOut, operation_id="updatePreferences")
async def update_preferences(userId: str, body: PreferencesUpdate, principal: Writer, db: Db) -> PreferencesOut:
    _own(principal, userId)
    if body.timezone is not None and not prefs.valid_timezone(body.timezone):
        raise _unprocessable("Unknown IANA time zone", "timezone")
    pref = await db.get(Preference, (principal.tenant_id, userId), with_for_update=True)
    now = datetime.now(UTC)
    if pref is None:
        pref = Preference(tenant_id=principal.tenant_id, user_id=userId, channels={}, marketing_opt_in=False)
        db.add(pref)
    fields = body.model_fields_set
    if body.locale is not None:
        pref.locale = body.locale
    if body.timezone is not None:
        pref.timezone = body.timezone
    if "quiet_hours" in fields:
        if body.quiet_hours is None:
            pref.quiet_start = pref.quiet_end = None
        else:
            pref.quiet_start = time.fromisoformat(body.quiet_hours.start)
            pref.quiet_end = time.fromisoformat(body.quiet_hours.end)
    if body.marketing_opt_in is not None:
        if body.marketing_opt_in and not pref.marketing_opt_in:
            pref.marketing_opt_in_at = now  # record when consent was given
        pref.marketing_opt_in = body.marketing_opt_in
    if body.channels:
        merged = {k: dict(v) for k, v in (pref.channels or {}).items()}
        for category, switches in body.channels.items():
            merged.setdefault(category, {}).update(switches.model_dump(exclude_none=True))
        pref.channels = merged
    pref.updated_at = now
    await db.commit()
    return _prefs_out(prefs.effective(userId, pref))


# ── device tokens ────────────────────────────────────────────────────────────


def _device_out(d: DeviceToken) -> DeviceTokenOut:
    return DeviceTokenOut(id=d.id, platform=d.platform, token_suffix=d.token[-6:], created_at=d.created_at)  # type: ignore[arg-type]


@router.post("/notification-devices", status_code=201, response_model=DeviceTokenOut, operation_id="registerDeviceToken")
async def register_device(body: DeviceTokenCreate, principal: Writer, db: Db) -> DeviceTokenOut:
    now = datetime.now(UTC)
    device = await db.scalar(
        select(DeviceToken).where(DeviceToken.tenant_id == principal.tenant_id, DeviceToken.token == body.token).with_for_update()
    )
    if device is None:
        device = DeviceToken(id=str(ULID()), tenant_id=principal.tenant_id, user_id=principal.user_id, platform=body.platform, token=body.token, created_at=now, last_seen_at=now)
        db.add(device)
    else:
        # A device belongs to whoever signed in on it last.
        device.user_id, device.platform, device.last_seen_at = principal.user_id, body.platform, now
    await db.commit()
    return _device_out(device)


@router.delete("/notification-devices/{id}", status_code=204, operation_id="deleteDeviceToken")
async def delete_device(id: str, principal: Writer, db: Db) -> Response:
    result = await db.execute(
        delete(DeviceToken).where(DeviceToken.id == id, DeviceToken.tenant_id == principal.tenant_id, DeviceToken.user_id == principal.user_id)
    )
    if not result.rowcount:
        raise _not_found("Device token")
    await db.commit()
    return Response(status_code=204)


# ── internal recipient links ─────────────────────────────────────────────────


@router.post("/notifications/recipient-links", status_code=201, response_model=RecipientLinkIn, operation_id="registerRecipientLink")
async def register_link(body: RecipientLinkIn, principal: Service, db: Db) -> RecipientLinkIn:
    from sqlalchemy.dialects.postgresql import insert

    tenant_id = body.tenant_id or principal.tenant_id
    await db.execute(
        insert(RecipientLink)
        .values(tenant_id=tenant_id, entity_type=body.entity_type, entity_id=body.entity_id, user_id=body.user_id, role=body.role)
        .on_conflict_do_update(index_elements=["tenant_id", "entity_type", "entity_id", "user_id"], set_={"role": body.role})
    )
    await db.commit()
    return body.model_copy(update={"tenant_id": tenant_id})


@router.delete(
    "/notifications/recipient-links/{entity_type}/{entity_id}/{user_id}", status_code=204, operation_id="removeRecipientLink"
)
async def remove_link(entity_type: str, entity_id: str, user_id: str, principal: Service, db: Db) -> Response:
    result = await db.execute(
        delete(RecipientLink).where(
            RecipientLink.tenant_id == principal.tenant_id,
            RecipientLink.entity_type == entity_type,
            RecipientLink.entity_id == entity_id,
            RecipientLink.user_id == user_id,
        )
    )
    if not result.rowcount:
        raise _not_found("Recipient link")
    await db.commit()
    return Response(status_code=204)
