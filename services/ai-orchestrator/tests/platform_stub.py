"""In-process stand-in for the platform services the assistant reads (httpx.MockTransport).

It answers the same URLs and shapes as provider-service, appointment-service, transformation-engine
and concierge-service, enforces "bearer required" where the real services do, and records every
request so tests can assert what was (and was not) sent.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import httpx

PROVIDER_OK = "01PROVIDERVERIFIED000000001"
PROVIDER_UNVERIFIED = "01PROVIDERUNVERIFIED0000002"
SERVICE_DENTAL = "01SERVICEDENTAL00000000001"
SERVICE_DENTAL_2 = "01SERVICEDENTAL00000000002"
SERVICE_UNVERIFIED = "01SERVICEUNVERIFIED0000003"
FACILITY = "01FACILITYVERIFIED00000001"
MILESTONE = "01MILESTONECONSULT00000001"
JOURNEY = "01JOURNEY00000000000000001"
APPOINTMENT = "01APPOINTMENT0000000000001"
CASE = "01CASE00000000000000000001"
TOKEN = "caller-access-token"


def _provider(pid: str, verified: bool) -> dict:
    return {
        "id": pid,
        "type": "doctor",
        "display_name": "Dr. Layla Haddad" if verified else "Dr. Unverified",
        "title": "Consultant Dentist",
        "specialties": ["dental"],
        "languages": ["en", "ar"],
        "status": "active",
        "verification_status": "verified" if verified else "under_review",
        "user_id": "owner-user-id-must-not-leak",
    }


def _service(sid: str, provider_id: str, name: str, amount_minor: int | None) -> dict:
    return {
        "id": sid,
        "provider_id": provider_id,
        "facility_id": FACILITY,
        "branch_id": "01BRANCH000000000000000001",
        "category": "dental",
        "name": name,
        "duration_minutes": 45,
        "mode": "in_person",
        "price_type": "fixed" if amount_minor is not None else "on_request",
        "price": {"amount_minor": amount_minor, "currency": "AED"} if amount_minor is not None else None,
        "professional_fee": None,
        "facility_fee": None,
        "status": "active",
    }


@dataclass
class PlatformStub:
    user_id: str = ""
    has_journey: bool = True
    requests: list[httpx.Request] = field(default_factory=list)
    cases_created: list[dict] = field(default_factory=list)
    fail_services: bool = False

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def paths(self) -> list[str]:
        return [f"{r.method} {r.url.path}" for r in self.requests]

    def _authed(self, request: httpx.Request) -> bool:
        return request.headers.get("authorization") == f"Bearer {TOKEN}"

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path, q = request.url.path, request.url.params
        services = {
            SERVICE_DENTAL: _service(SERVICE_DENTAL, PROVIDER_OK, "Dental check-up and cleaning", 45000),
            SERVICE_DENTAL_2: _service(SERVICE_DENTAL_2, PROVIDER_OK, "Smile design consultation", None),
            SERVICE_UNVERIFIED: _service(SERVICE_UNVERIFIED, PROVIDER_UNVERIFIED, "Cut-price veneers", 9900),
        }
        providers = {PROVIDER_OK: _provider(PROVIDER_OK, True), PROVIDER_UNVERIFIED: _provider(PROVIDER_UNVERIFIED, False)}
        facility = {"id": FACILITY, "type": "clinic", "name": "Marina Dental Clinic", "status": "active", "verification_status": "verified", "license_number": "must-not-leak"}

        if path == "/v1/services":
            if self.fail_services:
                return httpx.Response(503, json={"code": "service_unavailable"})
            data = [s for s in services.values() if s["category"] == q.get("category")]
            return httpx.Response(200, json={"data": data, "page": {"has_more": False}})
        if path.startswith("/v1/services/") and path.endswith("/slots"):
            sid = path.split("/")[3]
            if sid not in services:
                return httpx.Response(404, json={"code": "not_found"})
            slots = [
                {"scheduled_at": f"2030-01-0{d}T06:00:00Z", "ends_at": f"2030-01-0{d}T06:45:00Z", "local_start": f"2030-01-0{d}T10:00:00+04:00", "local_end": f"2030-01-0{d}T10:45:00+04:00"}
                for d in range(2, 7)
            ]
            return httpx.Response(200, json={"service_id": sid, "provider_id": PROVIDER_OK, "branch_id": "b", "timezone": "Asia/Dubai", "duration_minutes": 45, "buffer_minutes": 0, "from": q.get("from"), "to": q.get("to"), "slots": slots})
        if path.startswith("/v1/services/"):
            service = services.get(path.split("/")[3])
            return httpx.Response(200, json=service) if service else httpx.Response(404, json={"code": "not_found"})
        if path == "/v1/providers":
            return httpx.Response(200, json={"data": list(providers.values()), "page": {"has_more": False}})
        if path.startswith("/v1/providers/"):
            provider = providers.get(path.split("/")[3])
            return httpx.Response(200, json=provider) if provider else httpx.Response(404, json={"code": "not_found"})
        if path == "/v1/facilities":
            return httpx.Response(200, json={"data": [facility], "page": {"has_more": False}})
        if path.startswith("/v1/facilities/"):
            return httpx.Response(200, json=facility) if path.endswith(FACILITY) else httpx.Response(404, json={"code": "not_found"})

        # Everything below is the caller's own data: bearer required, like the real services.
        if not self._authed(request):
            return httpx.Response(401, json={"code": "unauthorized"})
        if path == f"/v1/journeys/{self.user_id}":
            if not self.has_journey:
                return httpx.Response(404, json={"code": "not_found"})
            return httpx.Response(200, json={"id": JOURNEY, "user_id": self.user_id, "primary_goals": ["dental_smile"], "status": "active"})
        if path.startswith("/v1/journeys/") and path.endswith("/roadmap"):
            step = {"id": MILESTONE, "title": "Consultation", "status": "pending", "code": "consultation", "goal": "dental_smile", "service_category": "dental", "sequence": 2}
            done = {"id": "01MILESTONEINTAKE000000001", "title": "Intake", "status": "completed", "code": "intake_assessment", "goal": None, "service_category": None, "sequence": 1}
            return httpx.Response(200, json={"journey_id": JOURNEY, "phases": [{"id": "p1", "code": "consult", "name": "Consult", "sequence": 1, "status": "in_progress", "milestones": [done, step]}]})
        if path.startswith("/v1/journeys/") and path.endswith("/next-actions"):
            return httpx.Response(200, json=[{"action_type": "book", "priority": "high", "milestone_id": MILESTONE, "milestone_code": "consultation", "goal": "dental_smile", "service_category": "dental"}])
        if path.startswith("/v1/journeys/"):
            return httpx.Response(403, json={"code": "forbidden"})
        if path == "/v1/appointments":
            if q.get("user_id") != self.user_id:
                return httpx.Response(403, json={"code": "forbidden"})
            appointment = {"id": APPOINTMENT, "user_id": self.user_id, "service_id": SERVICE_DENTAL, "service_name": "Dental check-up and cleaning", "status": "confirmed", "scheduled_at": "2030-01-02T06:00:00Z", "local_start": "2030-01-02T10:00:00+04:00", "timezone": "Asia/Dubai", "price": {"amount_minor": 45000, "currency": "AED"}}
            return httpx.Response(200, json={"data": [appointment], "page": {"has_more": False}})
        if path == "/v1/concierge/cases" and request.method == "POST":
            body = json.loads(request.content)
            self.cases_created.append({"body": body, "idempotency_key": request.headers.get("idempotency-key")})
            return httpx.Response(201, json={"id": CASE, "status": "submitted", "category": body["category"], "first_response_due_at": "2030-01-01T10:00:00Z"})
        if path == f"/v1/concierge/cases/{CASE}":
            return httpx.Response(200, json={"id": CASE, "status": "triaged", "first_response_due_at": "2030-01-01T10:00:00Z"})
        return httpx.Response(404, json={"code": "not_found"})
