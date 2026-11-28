"""provider-service client at the HTTP boundary: service token, fail-closed behaviour, no trust in drift."""

from __future__ import annotations

import json

import httpx
import pytest

from profile_service.clients.organisations import DirectoryUnavailable, HttpOrganisationDirectory, ServiceTokenSource

TOKEN_URL = "http://identity.test/v1/auth/service-token"
BASE = "http://provider.test"


def _directory(handler) -> tuple[HttpOrganisationDirectory, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(record))
    tokens = ServiceTokenSource(client=client, token_url=TOKEN_URL, client_id="healuxa-internal", client_secret="s3cret")
    return HttpOrganisationDirectory(client=client, base_url=BASE, tokens=tokens), seen


def _token(request: httpx.Request) -> httpx.Response | None:
    if str(request.url) == TOKEN_URL:
        assert request.headers["X-Service-Client-Id"] == "healuxa-internal"
        return httpx.Response(200, json={"access_token": "svc-token", "expires_in": 300})
    return None


async def test_actor_uses_service_token_and_tenant() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if (r := _token(request)) is not None:
            return r
        assert request.headers["Authorization"] == "Bearer svc-token"
        assert request.url.path == "/v1/internal/records-access/actors/01JUSER000000000000000001"
        assert request.url.params["tenant_id"] == "healuxa-dubai"
        return httpx.Response(
            200,
            json={
                "user_id": "01JUSER000000000000000001",
                "providers": [{"id": "01JPROV000000000000000001", "status": "active", "verification_status": "verified"}],
                "facilities": [{"id": "01JFAC0000000000000000001", "role": "scheduler", "status": "active", "verification_status": "verified"}],
            },
        )

    directory, seen = _directory(handler)
    actor = await directory.actor("healuxa-dubai", "01JUSER000000000000000001")
    assert [p.id for p in actor.providers] == ["01JPROV000000000000000001"]
    assert actor.facilities[0].role == "scheduler"
    await directory.actor("healuxa-dubai", "01JUSER000000000000000001")
    assert sum(1 for r in seen if str(r.url) == TOKEN_URL) == 1  # token cached


async def test_expired_token_is_refreshed_once() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == TOKEN_URL:
            calls["n"] += 1
            return httpx.Response(200, json={"access_token": f"t{calls['n']}", "expires_in": 300})
        if request.headers["Authorization"] == "Bearer t1":
            return httpx.Response(401, json={})
        return httpx.Response(200, json={"user_id": "u-000000001", "providers": [], "facilities": []})

    directory, _ = _directory(handler)
    actor = await directory.actor("healuxa-dubai", "u-000000001")
    assert actor.providers == [] and calls["n"] == 2


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, json={}),
        httpx.Response(403, json={}),
        httpx.Response(404, json={}),  # missing endpoint must not read as "no memberships"
        httpx.Response(200, text="not json"),
        httpx.Response(200, json={"providers": "nope"}),
        httpx.Response(200, json={"user_id": "someone-else", "providers": [], "facilities": []}),
    ],
)
async def test_actor_fails_closed(response: httpx.Response) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _token(request) or response

    directory, _ = _directory(handler)
    with pytest.raises(DirectoryUnavailable):
        await directory.actor("healuxa-dubai", "u-000000001")


async def test_unreachable_provider_or_token_issuer_fails_closed() -> None:
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    directory, _ = _directory(down)
    with pytest.raises(DirectoryUnavailable):
        await directory.actor("healuxa-dubai", "u-000000001")

    def no_token(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={}) if str(request.url) == TOKEN_URL else httpx.Response(200, json={})

    directory, _ = _directory(no_token)
    with pytest.raises(DirectoryUnavailable):
        await directory.actor("healuxa-dubai", "u-000000001")


async def test_grantee_lookup() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if (r := _token(request)) is not None:
            return r
        if request.url.path.endswith("/missing0001"):
            return httpx.Response(404, json={})
        _, _, _, _, _, kind, gid = request.url.path.split("/")
        body = {"type": kind, "id": gid, "name": "Marina Clinic", "status": "active", "verification_status": "verified"}
        if gid == "drifted0001":
            body["id"] = "other00001"
        return httpx.Response(200, content=json.dumps(body))

    directory, _ = _directory(handler)
    found = await directory.grantee("healuxa-dubai", "facility", "fac0000001")
    assert found is not None and found.name == "Marina Clinic"
    assert await directory.grantee("healuxa-dubai", "facility", "missing0001") is None
    with pytest.raises(DirectoryUnavailable):
        await directory.grantee("healuxa-dubai", "facility", "drifted0001")


async def test_api_wires_the_http_directory_through_dependency(client, monkeypatch) -> None:
    """End to end through the app with only the network mocked: membership decides access."""
    from profile_service.api import records as records_api
    from records_helpers import customer, grant, new_id, ok, practice, uploaded

    owner, doctor, provider_id = new_id(), new_id(), new_id()

    def handler(request: httpx.Request) -> httpx.Response:
        if (r := _token(request)) is not None:
            return r
        path = request.url.path
        if path.startswith("/v1/internal/records-access/grantees/provider/"):
            return httpx.Response(200, json={"type": "provider", "id": provider_id, "name": "Dr. Real", "status": "active", "verification_status": "verified"})
        user = path.rsplit("/", 1)[-1]
        providers = [{"id": provider_id, "status": "active", "verification_status": "verified"}] if user == doctor else []
        return httpx.Response(200, json={"user_id": user, "providers": providers, "facilities": []})

    directory, seen = _directory(handler)
    monkeypatch.setattr(records_api, "_directory", directory)
    record = await uploaded(client, customer(owner))
    await ok(await grant(client, customer(owner), grantee_type="provider", grantee_id=provider_id, record_ids=[record["id"]]), 201)
    assert (await client.get(f"/v1/records/{record['id']}/content", headers=practice(doctor))).status_code == 200
    assert (await client.get(f"/v1/records/{record['id']}/content", headers=practice(new_id()))).status_code == 404
    assert any(r.url.path.endswith(f"/actors/{doctor}") for r in seen)
