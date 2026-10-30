"""HttpProviderDirectory against a mocked provider-service + identity token endpoint."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from appointment_service.clients.provider_directory import HttpProviderDirectory, ProviderUnavailable, ServiceTokenSource

CONTEXT = {
    "offering": {
        "id": "01HSERVICE0000000000000000", "provider_id": "01HPROVIDER000000000000000", "facility_id": "01HFACILITY000000000000000",
        "branch_id": "01HBRANCH00000000000000000", "name": "Consultation", "category": "consultation", "duration_minutes": 30,
        "buffer_minutes": 10, "mode": "in_person", "status": "active", "price_type": "fixed",
        "professional_fee_minor": 50000, "facility_fee_minor": 10000, "currency": "AED",
    },
    "provider": {"id": "01HPROVIDER000000000000000", "user_id": "01HOWNER000000000000000000", "status": "active", "verification_status": "verified"},
    "facility": {"id": "01HFACILITY000000000000000", "status": "active", "verification_status": "verified"},
    "branch": {"id": "01HBRANCH00000000000000000", "facility_id": "01HFACILITY000000000000000", "timezone": "Asia/Dubai", "status": "active"},
    "affiliation_active": True,
    "bookable": True,
    "operating_hours": [{"weekday": 0, "start_minute": 540, "end_minute": 1080}],
    "availability_rules": [{"id": "r1", "weekday": 0, "start_minute": 540, "end_minute": 720, "effective_from": "2027-01-01", "effective_until": None}],
    "exceptions": [],
}
WINDOW = (datetime(2027, 3, 1, tzinfo=UTC), datetime(2027, 3, 3, tzinfo=UTC))


def _directory(handler) -> tuple[HttpProviderDirectory, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(record))
    tokens = ServiceTokenSource(client=client, token_url="http://identity/v1/auth/service-token", client_id="healuxa-internal", client_secret="s3cret")
    return HttpProviderDirectory(client=client, base_url="http://provider/", tokens=tokens), seen


def _token(request: httpx.Request) -> httpx.Response | None:
    if request.url.path == "/v1/auth/service-token":
        assert request.headers["X-Service-Client-Id"] == "healuxa-internal"
        return httpx.Response(200, json={"access_token": "svc-token", "token_type": "Bearer", "expires_in": 900})
    return None


async def test_fetches_context_with_cached_service_token() -> None:
    def handler(request):
        if (resp := _token(request)) is not None:
            return resp
        assert request.headers["Authorization"] == "Bearer svc-token"
        assert request.url.params["tenant_id"] == "healuxa-dubai" and request.url.params["from"].startswith("2027-03-01T00:00:00")
        return httpx.Response(200, json=CONTEXT)

    directory, seen = _directory(handler)
    context = await directory.scheduling_context("healuxa-dubai", "01HSERVICE0000000000000000", *WINDOW)
    await directory.scheduling_context("healuxa-dubai", "01HSERVICE0000000000000000", *WINDOW)
    assert context is not None and context.offering.price_minor == 60000 and context.branch.timezone == "Asia/Dubai"
    assert [r.url.path for r in seen].count("/v1/auth/service-token") == 1


async def test_missing_offering_is_none_and_actor_parses() -> None:
    def handler(request):
        if (resp := _token(request)) is not None:
            return resp
        if "/actors/" in request.url.path:
            return httpx.Response(200, json={"user_id": "u1", "provider_ids": ["p1"], "facility_roles": [{"facility_id": "f1", "role": "scheduler"}]})
        return httpx.Response(404, json={"code": "not_found"})

    directory, _ = _directory(handler)
    assert await directory.scheduling_context("healuxa-dubai", "x", *WINDOW) is None
    actor = await directory.actor("healuxa-dubai", "u1")
    assert actor.provider_ids == ["p1"] and actor.facility_roles[0].role == "scheduler"


async def test_rejected_token_is_refreshed_once() -> None:
    calls = {"provider": 0}

    def handler(request):
        if (resp := _token(request)) is not None:
            return resp
        calls["provider"] += 1
        return httpx.Response(401) if calls["provider"] == 1 else httpx.Response(200, json=CONTEXT)

    directory, seen = _directory(handler)
    assert await directory.scheduling_context("healuxa-dubai", "s", *WINDOW) is not None
    assert [r.url.path for r in seen].count("/v1/auth/service-token") == 2


@pytest.mark.parametrize(
    "failure",
    [
        lambda request: (_ for _ in ()).throw(httpx.ConnectTimeout("timeout", request=request)),
        lambda request: httpx.Response(503),
        lambda request: httpx.Response(200, json={"offering": "garbage"}),
        lambda request: httpx.Response(401),
    ],
    ids=["timeout", "5xx", "malformed", "unauthorised"],
)
async def test_failures_raise_provider_unavailable(failure) -> None:
    def handler(request):
        if (resp := _token(request)) is not None:
            return resp
        return failure(request)

    directory, _ = _directory(handler)
    with pytest.raises(ProviderUnavailable):
        await directory.scheduling_context("healuxa-dubai", "s", *WINDOW)


async def test_token_endpoint_failure_is_unavailable() -> None:
    directory, _ = _directory(lambda request: httpx.Response(401))
    with pytest.raises(ProviderUnavailable):
        await directory.actor("healuxa-dubai", "u1")
