"""In-app inbox API, internal direct send, consent and idempotency."""

from __future__ import annotations

from httpx import AsyncClient

from helpers import OTHER_TENANT, deliveries, new_id, notifications_of, ok, send, service, set_prefs, user


async def test_send_creates_inbox_entry_and_queued_deliveries(client: AsyncClient) -> None:
    uid = new_id()
    result = await send(client, uid)
    assert {d["channel"]: d["status"] for d in result["deliveries"]} == {"in_app": "sent", "email": "pending", "push": "pending"}
    inbox = await ok(await client.get("/v1/notifications", headers=user(uid)))
    [item] = inbox["data"]
    assert item["id"] == result["notification_id"] and item["template"] == "account.notice" and item["read_at"] is None
    assert item["title"] == "Account notice" and item["locale"] == "en"


async def test_send_uses_user_locale(client: AsyncClient) -> None:
    uid = new_id()
    await set_prefs(client, uid, {"locale": "ar"})
    await send(client, uid)
    [item] = (await ok(await client.get("/v1/notifications", headers=user(uid))))["data"]
    assert item["locale"] == "ar" and item["title"] == "إشعار الحساب"


async def test_send_is_service_only(client: AsyncClient) -> None:
    uid = new_id()
    response = await client.post("/v1/notifications/send", json={"user_id": uid, "template": "account.notice"}, headers=user(uid))
    assert response.status_code == 403


async def test_send_idempotency_key_replays(client: AsyncClient) -> None:
    uid = new_id()
    first = await send(client, uid, key="send-key-000001")
    second = await send(client, uid, key="send-key-000001")
    assert first["notification_id"] == second["notification_id"]
    assert len(await notifications_of(uid)) == 1 and len(await deliveries(uid)) == 3
    conflict = await send(client, uid, "marketing.newsletter", key="send-key-000001", expect=409)
    assert conflict["code"] == "idempotency_conflict"


async def test_send_rejects_unknown_template_and_unsafe_data(client: AsyncClient) -> None:
    uid = new_id()
    await send(client, uid, "does.not.exist", expect=422)
    await send(client, uid, "account.notice", data={"diagnosis": "x"}, expect=422)
    await send(client, uid, "concierge.case_status_changed", data={"status": "x" * 201}, expect=422)
    await send(client, uid, "concierge.case_status_changed", data={"status": {"nested": True}}, expect=422)


async def test_opted_out_channel_is_never_queued(client: AsyncClient, worker) -> None:
    uid = new_id()
    await set_prefs(client, uid, {"channels": {"account": {"email": False}}})
    result = await send(client, uid)
    by_channel = {d["channel"]: d for d in result["deliveries"]}
    assert by_channel["email"]["status"] == "skipped" and by_channel["email"]["skip_reason"] == "opted_out"
    await worker.run_once()
    email = (await deliveries(uid))["email"]
    assert email.status == "skipped" and email.attempts == 0
    assert all(m.user_id != uid for m in worker.registry.get("email").sent)


async def test_marketing_is_off_by_default(client: AsyncClient, worker) -> None:
    uid = new_id()
    result = await send(client, uid, "marketing.newsletter")
    assert {d["status"] for d in result["deliveries"]} == {"skipped"}
    assert {d["skip_reason"] for d in result["deliveries"]} == {"no_marketing_consent"}
    assert (await ok(await client.get("/v1/notifications", headers=user(uid))))["data"] == []
    await worker.run_once()
    assert all(m.user_id != uid for m in worker.registry.get("email").sent)


async def test_marketing_after_consent_is_delivered(client: AsyncClient) -> None:
    uid = new_id()
    await set_prefs(client, uid, {"marketing_opt_in": True})
    result = await send(client, uid, "marketing.newsletter")
    assert {d["channel"]: d["status"] for d in result["deliveries"]} == {"in_app": "sent", "email": "pending"}


async def test_send_channel_restriction_and_web_push_alias(client: AsyncClient) -> None:
    uid = new_id()
    result = await send(client, uid, channel="web_push")
    assert [(d["channel"], d["status"]) for d in result["deliveries"]] == [("push", "pending")]
    # Not in the inbox: in_app was not requested.
    assert (await ok(await client.get("/v1/notifications", headers=user(uid))))["data"] == []


async def test_inbox_is_per_user_and_tenant(client: AsyncClient) -> None:
    alice, bob = new_id(), new_id()
    await send(client, alice)
    await ok(await client.post("/v1/notifications/send", json={"user_id": alice, "template": "account.notice"}, headers=service(tenant_id=OTHER_TENANT)), 202)
    assert len((await ok(await client.get("/v1/notifications", headers=user(alice))))["data"]) == 1
    assert (await ok(await client.get("/v1/notifications", headers=user(bob))))["data"] == []
    assert len((await ok(await client.get("/v1/notifications", headers=user(alice, tenant_id=OTHER_TENANT))))["data"]) == 1


async def test_unread_count_mark_read_and_read_all(client: AsyncClient) -> None:
    uid = new_id()
    ids = [(await send(client, uid))["notification_id"] for _ in range(3)]
    assert await ok(await client.get("/v1/notifications/unread-count", headers=user(uid))) == {"unread": 3}
    read = await ok(await client.post(f"/v1/notifications/{ids[0]}/read", headers=user(uid)))
    assert read["read_at"] is not None
    again = await ok(await client.post(f"/v1/notifications/{ids[0]}/read", headers=user(uid)))
    assert again["read_at"] == read["read_at"]
    assert await ok(await client.get("/v1/notifications/unread-count", headers=user(uid))) == {"unread": 2}
    unread = await ok(await client.get("/v1/notifications", params={"unread_only": "true"}, headers=user(uid)))
    assert {n["id"] for n in unread["data"]} == set(ids[1:])
    assert await ok(await client.post("/v1/notifications/read-all", headers=user(uid))) == {"marked": 2}
    assert await ok(await client.get("/v1/notifications/unread-count", headers=user(uid))) == {"unread": 0}


async def test_cannot_mark_someone_elses_notification(client: AsyncClient) -> None:
    owner = new_id()
    nid = (await send(client, owner))["notification_id"]
    assert (await client.post(f"/v1/notifications/{nid}/read", headers=user(new_id()))).status_code == 404
    assert (await client.post(f"/v1/notifications/{nid}/read", headers=user(owner, tenant_id=OTHER_TENANT))).status_code == 404


async def test_inbox_pagination_and_category_filter(client: AsyncClient) -> None:
    uid = new_id()
    ids = [(await send(client, uid))["notification_id"] for _ in range(5)]
    await send(client, uid, "concierge.message_posted")
    page1 = await ok(await client.get("/v1/notifications", params={"limit": 2, "category": "account"}, headers=user(uid)))
    page2 = await ok(await client.get("/v1/notifications", params={"limit": 2, "category": "account", "cursor": page1["page"]["next_cursor"]}, headers=user(uid)))
    page3 = await ok(await client.get("/v1/notifications", params={"limit": 2, "category": "account", "cursor": page2["page"]["next_cursor"]}, headers=user(uid)))
    assert [n["id"] for n in page1["data"] + page2["data"] + page3["data"]] == list(reversed(ids))
    assert page3["page"]["has_more"] is False
    concierge = await ok(await client.get("/v1/notifications", params={"category": "concierge"}, headers=user(uid)))
    assert [n["template"] for n in concierge["data"]] == ["concierge.message_posted"]
