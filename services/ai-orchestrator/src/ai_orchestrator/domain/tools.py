"""Tools the model may call, executed server-side with the caller's identity, and the action cards.

Grounding rule (enforced here, not in the prompt): a card can only be built from an entity that a
tool returned **in this turn** (``TurnContext``). The model references entities by id through
``present_cards``; titles, prices, slots and links come from the tool data, never from model text.
Ids the tools did not return are dropped.

Tool results sent to the model are projected to the minimum needed for coordination: no user id,
no contact details, no licence numbers, no free-text notes.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from urllib.parse import quote

from ai_orchestrator.config import settings
from ai_orchestrator.infra.platform import PlatformClient, PlatformError

ID_PATTERN = re.compile(r"^[A-Za-z0-9-]{10,36}$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
BOOKABLE_STEP_CODES = ("consultation", "care", "follow_up")
OPEN_APPOINTMENT_STATUSES = ("held", "requested", "confirmed", "rescheduled", "checked_in")
HANDOFF_CATEGORIES = ("medical_travel", "specialist_search", "second_opinion_coordination", "logistics", "other")
CARD_KINDS = ("service", "provider", "facility", "journey_step", "appointment")
# Categories used by journey plans (transformation-engine GOAL_CATEGORIES); the catalog may hold others.
KNOWN_CATEGORIES = (
    "dermatology",
    "aesthetics",
    "hair",
    "dental",
    "nutrition",
    "physiotherapy",
    "general practice",
    "longevity",
    "mental wellbeing",
)

HANDOFF_CARD: dict[str, Any] = {"kind": "handoff", "href": "/account/concierge#new"}


def _obj(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


_NULLABLE_STR = {"type": ["string", "null"]}

# Order is part of the cached prompt prefix: keep it stable.
TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "search_services",
        "description": (
            "Search Healuxa's verified, bookable services by catalog category. Returns real names, durations and prices. "
            "Known categories: " + ", ".join(KNOWN_CATEGORIES) + ". Use the service_category of a journey step when there is one."
        ),
        "strict": True,
        "input_schema": _obj({"category": {"type": "string", "description": "Catalog category, lowercase."}}, ["category"]),
    },
    {
        "name": "get_service",
        "description": "Get one verified service by id (name, duration, real price, provider).",
        "strict": True,
        "input_schema": _obj({"service_id": {"type": "string"}}, ["service_id"]),
    },
    {
        "name": "get_service_slots",
        "description": (
            "Real bookable time slots of a service for the next two weeks (or the given branch-local dates, at most 31 days). "
            "Availability may only be mentioned after calling this."
        ),
        "strict": True,
        "input_schema": _obj(
            {
                "service_id": {"type": "string"},
                "from_date": {**_NULLABLE_STR, "description": "YYYY-MM-DD or null for today."},
                "to_date": {**_NULLABLE_STR, "description": "YYYY-MM-DD or null for two weeks ahead."},
            },
            ["service_id", "from_date", "to_date"],
        ),
    },
    {
        "name": "search_providers",
        "description": "Search verified practitioners. All filters are optional (pass null).",
        "strict": True,
        "input_schema": _obj(
            {
                "specialty": _NULLABLE_STR,
                "language": {**_NULLABLE_STR, "description": "Language code such as en, ar, fa."},
                "city": _NULLABLE_STR,
            },
            ["specialty", "language", "city"],
        ),
    },
    {
        "name": "get_provider",
        "description": "Get one verified practitioner by id.",
        "strict": True,
        "input_schema": _obj({"provider_id": {"type": "string"}}, ["provider_id"]),
    },
    {
        "name": "search_facilities",
        "description": "Search verified clinics and hospitals. The city filter is optional (pass null).",
        "strict": True,
        "input_schema": _obj({"city": _NULLABLE_STR}, ["city"]),
    },
    {
        "name": "get_facility",
        "description": "Get one verified clinic or hospital by id.",
        "strict": True,
        "input_schema": _obj({"facility_id": {"type": "string"}}, ["facility_id"]),
    },
    {
        "name": "get_my_journey",
        "description": "The customer's own journey: goals, plan steps with status, and the next actions.",
        "strict": True,
        "input_schema": _obj({}, []),
    },
    {
        "name": "list_my_appointments",
        "description": "The customer's own upcoming appointments.",
        "strict": True,
        "input_schema": _obj({}, []),
    },
    {
        "name": "request_human_handoff",
        "description": (
            "Hand the conversation to a human coordinator by opening a concierge request. Use when the customer asks for a person "
            "or when you cannot help. Never include medical details."
        ),
        "strict": True,
        "input_schema": _obj({"category": {"type": "string", "enum": list(HANDOFF_CATEGORIES)}}, ["category"]),
    },
    {
        "name": "present_cards",
        "description": (
            "Show action cards to the customer for entities returned by tools in THIS turn (services, providers, facilities, "
            "journey steps, appointments). Cards carry the verified name, price, next slots and the booking link, so do not "
            "repeat those in text. Pass milestone_id with a service to link the booking to that journey step."
        ),
        "strict": True,
        "input_schema": _obj(
            {
                "cards": {
                    "type": "array",
                    "items": _obj(
                        {
                            "kind": {"type": "string", "enum": list(CARD_KINDS)},
                            "id": {"type": "string"},
                            "milestone_id": _NULLABLE_STR,
                        },
                        ["kind", "id", "milestone_id"],
                    ),
                }
            },
            ["cards"],
        ),
    },
]

TOOL_NAMES = tuple(tool["name"] for tool in TOOL_DEFINITIONS)


@dataclass
class ToolOutcome:
    name: str
    content: str
    is_error: bool = False


@dataclass
class TurnContext:
    """Per-turn registry of verified entities. Lives for one turn only."""

    user_id: str
    locale: str
    session_id: str
    handoff_case_id: str | None
    platform: PlatformClient
    today: date = field(default_factory=lambda: datetime.now(UTC).date())
    services: dict[str, dict] = field(default_factory=dict)
    providers: dict[str, dict] = field(default_factory=dict)
    facilities: dict[str, dict] = field(default_factory=dict)
    steps: dict[str, dict] = field(default_factory=dict)
    appointments: dict[str, dict] = field(default_factory=dict)
    slots: dict[str, dict] = field(default_factory=dict)
    case: dict | None = None
    cards: list[dict] = field(default_factory=list)
    rejected_cards: int = 0
    calls: list[dict] = field(default_factory=list)

    def grounded_amounts(self) -> set[Decimal]:
        amounts: set[Decimal] = set()
        for service in self.services.values():
            for key in ("price", "professional_fee", "facility_fee"):
                money = service.get(key)
                if money:
                    amounts.add(Decimal(money["amount"]))
        for appointment in self.appointments.values():
            if appointment.get("price"):
                amounts.add(Decimal(appointment["price"]["amount"]))
        return amounts


def _money(value: Any) -> dict[str, str] | None:
    if not isinstance(value, dict) or not isinstance(value.get("amount_minor"), int) or not value.get("currency"):
        return None
    # Healuxa currencies (AED and peers) use two minor digits; amount is the decimal the model may quote.
    return {"amount_minor": value["amount_minor"], "amount": f"{Decimal(value['amount_minor']) / 100:.2f}", "currency": str(value["currency"])}


def _valid_id(value: Any) -> bool:
    return isinstance(value, str) and bool(ID_PATTERN.match(value))


def _is_verified(entity: dict) -> bool:
    return entity.get("verification_status") == "verified" and entity.get("status") == "active"


def _provider_view(raw: dict) -> dict:
    return {
        "id": raw["id"],
        "display_name": raw.get("display_name"),
        "title": raw.get("title"),
        "type": raw.get("type"),
        "specialties": list(raw.get("specialties") or [])[:8],
        "languages": list(raw.get("languages") or [])[:8],
    }


def _facility_view(raw: dict) -> dict:
    return {"id": raw["id"], "name": raw.get("name"), "type": raw.get("type")}


def _service_view(raw: dict, provider: dict | None) -> dict:
    return {
        "id": raw["id"],
        "name": raw.get("name"),
        "category": raw.get("category"),
        "duration_minutes": raw.get("duration_minutes"),
        "mode": raw.get("mode"),
        "price_type": raw.get("price_type"),
        "price": _money(raw.get("price")),
        "professional_fee": _money(raw.get("professional_fee")),
        "facility_fee": _money(raw.get("facility_fee")),
        "provider_id": raw.get("provider_id"),
        "provider_name": provider.get("display_name") if provider else None,
        "facility_id": raw.get("facility_id"),
    }


async def _provider_for(ctx: TurnContext, provider_id: str | None) -> dict | None:
    if not _valid_id(provider_id):
        return None
    if provider_id in ctx.providers:
        return ctx.providers[provider_id]
    try:
        raw = await ctx.platform.get_provider(provider_id)
    except PlatformError:
        return None
    if not _is_verified(raw):
        return None
    ctx.providers[provider_id] = _provider_view(raw)
    return ctx.providers[provider_id]


async def _register_service(ctx: TurnContext, raw: dict) -> dict | None:
    if not _valid_id(raw.get("id")) or raw.get("status") != "active":
        return None
    provider = await _provider_for(ctx, raw.get("provider_id"))
    if provider is None:  # only offerings of verified, active practitioners are ever shown
        return None
    view = _service_view(raw, provider)
    ctx.services[view["id"]] = view
    return view


async def _search_services(ctx: TurnContext, args: dict) -> Any:
    category = str(args.get("category") or "").strip().lower()[:80]
    if len(category) < 2:
        raise PlatformError("invalid_request")
    raw = await ctx.platform.list_services(category=category, provider_id=None, facility_id=None, limit=6)
    views = [v for v in await asyncio.gather(*(_register_service(ctx, item) for item in raw[:6])) if v]
    return {"category": category, "services": views}


async def _get_service(ctx: TurnContext, args: dict) -> Any:
    view = await _register_service(ctx, await ctx.platform.get_service(args["service_id"]))
    if view is None:
        raise PlatformError("not_found")
    return view


def _clamp_dates(ctx: TurnContext, from_date: Any, to_date: Any) -> tuple[date, date]:
    start = ctx.today
    if isinstance(from_date, str) and DATE_PATTERN.match(from_date):
        try:
            start = max(ctx.today, date.fromisoformat(from_date))
        except ValueError:
            pass
    end = start + timedelta(days=settings.slot_lookahead_days)
    if isinstance(to_date, str) and DATE_PATTERN.match(to_date):
        try:
            end = date.fromisoformat(to_date)
        except ValueError:
            pass
    end = min(max(end, start), start + timedelta(days=30))
    return start, end


async def _get_service_slots(ctx: TurnContext, args: dict) -> Any:
    service_id = args["service_id"]
    if service_id not in ctx.services:
        await _get_service(ctx, {"service_id": service_id})
    start, end = _clamp_dates(ctx, args.get("from_date"), args.get("to_date"))
    raw = await ctx.platform.list_slots(service_id, date_from=start.isoformat(), date_to=end.isoformat())
    slots = [
        {"local_start": s.get("local_start"), "local_end": s.get("local_end"), "scheduled_at": s.get("scheduled_at")}
        for s in (raw.get("slots") or [])
        if s.get("local_start") and s.get("scheduled_at")
    ]
    view = {"service_id": service_id, "timezone": raw.get("timezone"), "from": start.isoformat(), "to": end.isoformat(), "slots": slots[:12], "total": len(slots)}
    ctx.slots[service_id] = view
    return view


async def _search_providers(ctx: TurnContext, args: dict) -> Any:
    def clean(key: str) -> str | None:
        value = args.get(key)
        return value.strip()[:80] if isinstance(value, str) and value.strip() else None

    raw = await ctx.platform.search_providers(specialty=clean("specialty"), language=clean("language"), city=clean("city"), type_=None, limit=6)
    views = []
    for item in raw[:6]:
        if _valid_id(item.get("id")) and _is_verified(item):
            ctx.providers[item["id"]] = _provider_view(item)
            views.append(ctx.providers[item["id"]])
    return {"providers": views}


async def _get_provider(ctx: TurnContext, args: dict) -> Any:
    raw = await ctx.platform.get_provider(args["provider_id"])
    if not _is_verified(raw):
        raise PlatformError("not_found")
    ctx.providers[raw["id"]] = _provider_view(raw)
    return ctx.providers[raw["id"]]


async def _search_facilities(ctx: TurnContext, args: dict) -> Any:
    city = args.get("city")
    raw = await ctx.platform.search_facilities(city=city.strip()[:80] if isinstance(city, str) and city.strip() else None, type_=None, limit=6)
    views = []
    for item in raw[:6]:
        if _valid_id(item.get("id")) and _is_verified(item):
            ctx.facilities[item["id"]] = _facility_view(item)
            views.append(ctx.facilities[item["id"]])
    return {"facilities": views}


async def _get_facility(ctx: TurnContext, args: dict) -> Any:
    raw = await ctx.platform.get_facility(args["facility_id"])
    if not _is_verified(raw):
        raise PlatformError("not_found")
    ctx.facilities[raw["id"]] = _facility_view(raw)
    return ctx.facilities[raw["id"]]


def _step_view(raw: dict) -> dict:
    return {
        "id": raw["id"],
        "code": raw.get("code"),
        "goal": raw.get("goal"),
        "status": raw.get("status"),
        "service_category": raw.get("service_category"),
        "scheduled_at": raw.get("scheduled_at"),
    }


async def _get_my_journey(ctx: TurnContext, _args: dict) -> Any:
    try:
        journey = await ctx.platform.get_journey(ctx.user_id)
    except PlatformError as exc:
        if exc.code == "not_found":
            return {"has_journey": False}
        raise
    journey_id = journey.get("id")
    if not _valid_id(journey_id):
        return {"has_journey": False}
    roadmap, actions = await asyncio.gather(ctx.platform.get_roadmap(journey_id), ctx.platform.get_next_actions(journey_id))
    phases = []
    for phase in roadmap.get("phases") or []:
        steps = []
        for milestone in phase.get("milestones") or []:
            if _valid_id(milestone.get("id")):
                ctx.steps[milestone["id"]] = _step_view(milestone)
                steps.append(ctx.steps[milestone["id"]])
        phases.append({"code": phase.get("code"), "status": phase.get("status"), "steps": steps})
    return {
        "has_journey": True,
        "status": journey.get("status"),
        "goals": list(journey.get("primary_goals") or []),
        "phases": phases,
        "next_actions": [
            {k: a.get(k) for k in ("action_type", "priority", "milestone_id", "milestone_code", "goal", "service_category")} for a in actions[:5]
        ],
    }


async def _list_my_appointments(ctx: TurnContext, _args: dict) -> Any:
    now = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    raw = await ctx.platform.list_my_appointments(user_id=ctx.user_id, date_from=now, limit=10)
    views = []
    for item in raw:
        if not _valid_id(item.get("id")) or item.get("status") not in OPEN_APPOINTMENT_STATUSES:
            continue
        view = {
            "id": item["id"],
            "service_name": item.get("service_name"),
            "status": item.get("status"),
            "local_start": item.get("local_start"),
            "scheduled_at": item.get("scheduled_at"),
            "timezone": item.get("timezone"),
            "price": _money(item.get("price")),
        }
        ctx.appointments[view["id"]] = view
        views.append(view)
    return {"appointments": views}


async def _request_human_handoff(ctx: TurnContext, args: dict) -> Any:
    category = args.get("category")
    if category not in HANDOFF_CATEGORIES:
        category = "other"
    if ctx.handoff_case_id:
        # One hand-off per session: point at the existing request instead of opening another.
        try:
            existing = await ctx.platform.get_concierge_case(ctx.handoff_case_id)
            ctx.case = {"id": existing["id"], "status": existing.get("status"), "first_response_due_at": existing.get("first_response_due_at")}
        except PlatformError:
            ctx.case = {"id": ctx.handoff_case_id, "status": None, "first_response_due_at": None}
        return {"handed_off": True, "already_open": True, "status": ctx.case["status"]}
    created = await ctx.platform.create_concierge_case(category=category, language=ctx.locale, idempotency_key=f"ai-handoff-{ctx.session_id}")
    if not _valid_id(created.get("id")):
        raise PlatformError("unavailable")
    ctx.case = {"id": created["id"], "status": created.get("status"), "first_response_due_at": created.get("first_response_due_at")}
    ctx.handoff_case_id = created["id"]
    return {"handed_off": True, "already_open": False, "status": ctx.case["status"], "first_response_due_at": ctx.case["first_response_due_at"]}


def _milestone_for(ctx: TurnContext, service: dict, requested: Any) -> str | None:
    """The journey step a booking of this service may be linked to — only an open, bookable step of the same category."""

    def fits(step: dict) -> bool:
        return (
            step.get("code") in BOOKABLE_STEP_CODES
            and step.get("status") in ("pending", "blocked")
            and bool(step.get("service_category"))
            and str(step["service_category"]).lower() == str(service.get("category") or "").lower()
        )

    if isinstance(requested, str) and requested in ctx.steps and fits(ctx.steps[requested]):
        return requested
    for step in ctx.steps.values():
        if fits(step):
            return step["id"]
    return None


def step_href(step: dict) -> str:
    if step.get("code") == "intake_assessment":
        return "/journey/intake"
    if step.get("code") in BOOKABLE_STEP_CODES and step.get("service_category") and step.get("status") != "completed":
        return f"/services?category={quote(str(step['service_category']))}&milestone={step['id']}"
    return "/journey"


def build_card(ctx: TurnContext, kind: str, entity_id: str, milestone_id: Any = None) -> dict | None:
    """Build one card strictly from this turn's verified registry; None when the id was not returned by a tool."""
    if kind == "service" and entity_id in ctx.services:
        service = ctx.services[entity_id]
        milestone = _milestone_for(ctx, service, milestone_id)
        slots = ctx.slots.get(entity_id)
        return {
            "kind": "service",
            "id": entity_id,
            "title": service["name"],
            "category": service["category"],
            "duration_minutes": service["duration_minutes"],
            "price_type": service["price_type"],
            "price": service["price"],
            "provider_id": service["provider_id"],
            "provider_name": service["provider_name"],
            "milestone_id": milestone,
            "next_slots": [s["scheduled_at"] for s in slots["slots"][:3]] if slots else [],
            "timezone": slots["timezone"] if slots else None,
            "href": f"/book/{entity_id}" + (f"?milestone={milestone}" if milestone else ""),
        }
    if kind == "provider" and entity_id in ctx.providers:
        provider = ctx.providers[entity_id]
        return {
            "kind": "provider",
            "id": entity_id,
            "title": provider["display_name"],
            "subtitle": provider["title"],
            "specialties": provider["specialties"][:4],
            "href": f"/providers/{entity_id}",
        }
    if kind == "facility" and entity_id in ctx.facilities:
        facility = ctx.facilities[entity_id]
        return {"kind": "facility", "id": entity_id, "title": facility["name"], "facility_type": facility["type"], "href": f"/facilities/{entity_id}"}
    if kind == "journey_step" and entity_id in ctx.steps:
        step = ctx.steps[entity_id]
        return {
            "kind": "journey_step",
            "id": entity_id,
            "code": step["code"],
            "goal": step["goal"],
            "status": step["status"],
            "service_category": step["service_category"],
            "href": step_href(step),
        }
    if kind == "appointment" and entity_id in ctx.appointments:
        appointment = ctx.appointments[entity_id]
        return {
            "kind": "appointment",
            "id": entity_id,
            "title": appointment["service_name"],
            "status": appointment["status"],
            "scheduled_at": appointment["scheduled_at"],
            "timezone": appointment["timezone"],
            "href": f"/account/bookings/{entity_id}",
        }
    return None


def case_card(case: dict) -> dict:
    return {
        "kind": "concierge_case",
        "id": case["id"],
        "status": case.get("status"),
        "first_response_due_at": case.get("first_response_due_at"),
        "href": f"/account/concierge/{case['id']}",
    }


async def _present_cards(ctx: TurnContext, args: dict) -> Any:
    shown, rejected = [], []
    requested = args.get("cards")
    for item in requested if isinstance(requested, list) else []:
        if not isinstance(item, dict):
            continue
        kind, entity_id = item.get("kind"), item.get("id")
        card = build_card(ctx, kind, entity_id, item.get("milestone_id")) if kind in CARD_KINDS and isinstance(entity_id, str) else None
        if card is None:
            ctx.rejected_cards += 1
            rejected.append(str(entity_id)[:40])
            continue
        if any(c["kind"] == card["kind"] and c["id"] == card["id"] for c in ctx.cards):
            continue
        if len(ctx.cards) >= settings.max_cards_per_turn:
            break
        ctx.cards.append(card)
        shown.append(card["id"])
    result: dict[str, Any] = {"shown": shown}
    if rejected:
        result["rejected"] = rejected
        result["note"] = "Rejected ids were not returned by a tool in this turn. Fetch them first; never invent ids."
    return result


_EXECUTORS = {
    "search_services": _search_services,
    "get_service": _get_service,
    "get_service_slots": _get_service_slots,
    "search_providers": _search_providers,
    "get_provider": _get_provider,
    "search_facilities": _search_facilities,
    "get_facility": _get_facility,
    "get_my_journey": _get_my_journey,
    "list_my_appointments": _list_my_appointments,
    "request_human_handoff": _request_human_handoff,
    "present_cards": _present_cards,
}

_ID_ARGS = {"get_service": "service_id", "get_service_slots": "service_id", "get_provider": "provider_id", "get_facility": "facility_id"}


async def execute_tool(ctx: TurnContext, name: str, args: Any) -> ToolOutcome:
    """Run one tool call. Never raises: failures become an error result the model can react to."""
    executor = _EXECUTORS.get(name)
    if executor is None or not isinstance(args, dict):
        ctx.calls.append({"name": str(name)[:64], "ok": False, "error": "invalid_request"})
        return ToolOutcome(name=str(name), content=json.dumps({"error": "invalid_request"}), is_error=True)
    id_arg = _ID_ARGS.get(name)
    if id_arg and not _valid_id(args.get(id_arg)):
        ctx.calls.append({"name": name, "ok": False, "error": "invalid_request"})
        return ToolOutcome(name=name, content=json.dumps({"error": "invalid_request"}), is_error=True)
    try:
        result = await executor(ctx, args)
    except PlatformError as exc:
        ctx.calls.append({"name": name, "ok": False, "error": exc.code})
        return ToolOutcome(name=name, content=json.dumps({"error": exc.code}), is_error=True)
    except (KeyError, TypeError, ValueError):
        ctx.calls.append({"name": name, "ok": False, "error": "unavailable"})
        return ToolOutcome(name=name, content=json.dumps({"error": "unavailable"}), is_error=True)
    ctx.calls.append({"name": name, "ok": True})
    return ToolOutcome(name=name, content=json.dumps(result, ensure_ascii=False, sort_keys=True))
