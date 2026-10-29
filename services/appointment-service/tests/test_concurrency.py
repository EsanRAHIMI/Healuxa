"""Exclusive slots are a database invariant, not just an application check."""

from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from ulid import ULID

from appointment_service.infra.db import SessionLocal
from appointment_service.infra.models import Appointment
from helpers import NOW, TUESDAY, FakeDirectory, customer, iso, local


async def _post_many(client: AsyncClient, practice, starts) -> list[int]:
    responses = await asyncio.gather(
        *(
            client.post("/v1/appointments", json={"service_id": practice.service_id, "scheduled_at": iso(s)}, headers=customer())
            for s in starts
        )
    )
    return sorted(r.status_code for r in responses)


async def test_ten_parallel_holds_on_one_slot_exactly_one_wins(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice(duration=30)
    codes = await _post_many(client, practice, [local(TUESDAY, "09:00")] * 10)
    assert codes == [201] + [409] * 9
    async with SessionLocal() as db:
        assert await db.scalar(select(func.count()).select_from(Appointment)) == 1


async def test_parallel_overlapping_slots_including_buffer_one_wins(client: AsyncClient, directory: FakeDirectory) -> None:
    practice = directory.add_practice(duration=30, buffer=15)
    # 09:00 occupies 09:00–09:45 and 09:30 occupies 09:30–10:15: they overlap through the buffer.
    codes = await _post_many(client, practice, [local(TUESDAY, "09:00"), local(TUESDAY, "09:30")] * 5)
    assert codes.count(201) == 1 and codes.count(409) == 9


def _row(provider_id: str, user_id: str, start, minutes: int, status: str = "held") -> Appointment:
    return Appointment(
        id=str(ULID()), tenant_id="healuxa-dubai", user_id=user_id, provider_id=provider_id, facility_id=str(ULID()),
        branch_id=str(ULID()), service_id=str(ULID()), status=status, starts_at=start, ends_at=start + timedelta(minutes=minutes),
        blocked_until=start + timedelta(minutes=minutes), timezone="Asia/Dubai", duration_minutes=minutes, buffer_minutes=0,
        payment_status="not_required", version=1, created_at=NOW, updated_at=NOW,
    )


async def test_database_rejects_overlap_even_bypassing_the_application() -> None:
    provider = str(ULID())
    start = NOW + timedelta(days=2)
    async with SessionLocal() as db:
        db.add(_row(provider, str(ULID()), start, 60))
        await db.commit()
    async with SessionLocal() as db:
        db.add(_row(provider, str(ULID()), start + timedelta(minutes=30), 60))
        with pytest.raises(IntegrityError, match="ex_appointments_provider_overlap"):
            await db.commit()
    # Adjacent ranges are fine ('[)' bounds) and freeing statuses never block.
    async with SessionLocal() as db:
        db.add(_row(provider, str(ULID()), start + timedelta(minutes=60), 30))
        db.add(_row(provider, str(ULID()), start, 60, status="cancelled"))
        db.add(_row(provider, str(ULID()), start, 60, status="rescheduled"))
        await db.commit()
