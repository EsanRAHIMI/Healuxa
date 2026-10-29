"""The implementation matches appointment.openapi.yaml and the event registry."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from appointment_service.events.publisher import APPOINTMENT_EVENTS
from appointment_service.infra.models import PAYMENT_STATUSES, STATUSES
from appointment_service.main import app

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = yaml.safe_load((ROOT / "packages/api-contracts/openapi/appointment.openapi.yaml").read_text())
METHODS = {"get", "post", "put", "patch", "delete"}


def _norm(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "{}", path)


def test_every_contract_operation_is_implemented_and_nothing_else() -> None:
    wanted = {(m, _norm("/v1" + p)) for p, ops in CONTRACT["paths"].items() for m in ops if m in METHODS}
    served = {
        (m, _norm(p))
        for p, ops in app.openapi()["paths"].items()
        for m in ops
        if p not in {"/health", "/ready", "/metrics"}
    }
    assert wanted == served
    assert len(wanted) == 7


def test_status_vocabularies_match_contract() -> None:
    schemas = CONTRACT["components"]["schemas"]
    assert tuple(schemas["AppointmentStatus"]["enum"]) == STATUSES
    assert tuple(schemas["PaymentStatus"]["enum"]) == PAYMENT_STATUSES


def test_published_events_are_registered_for_this_service() -> None:
    registry = (ROOT / "packages/event-contracts/src/registry.ts").read_text()
    for event_type, definition in APPOINTMENT_EVENTS.items():
        line = next(l for l in registry.splitlines() if f'type: "{event_type}"' in l)
        assert 'owner: "appointment-service"' in line and definition in line
