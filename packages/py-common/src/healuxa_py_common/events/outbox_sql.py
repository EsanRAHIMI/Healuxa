"""PostgreSQL outbox store (SQLAlchemy async). Each service owns its table via its own Alembic migration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import (
    Column,
    DateTime,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    func,
    insert,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from healuxa_py_common.events.envelope import EventEnvelope
from healuxa_py_common.events.outbox import STATUS_PENDING, STATUS_PUBLISHED, OutboxMessage, outbox_fields

OUTBOX_TABLE = "outbox_events"


def outbox_table(metadata: MetaData) -> Table:
    return Table(
        OUTBOX_TABLE,
        metadata,
        Column("event_id", String(64), primary_key=True),
        Column("event_type", String(128), nullable=False),
        Column("subject", String(255), nullable=False),
        Column("tenant_id", String(64), nullable=False),
        Column("body", JSONB, nullable=False),
        Column("status", String(16), nullable=False),
        Column("attempts", Integer, nullable=False, server_default="0"),
        Column("available_at", DateTime(timezone=True), nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("published_at", DateTime(timezone=True)),
        Column("last_error", Text),
        Index("ix_outbox_events_pending", "status", "available_at"),
    )


async def enqueue(session: AsyncSession, table: Table, envelope: EventEnvelope) -> None:
    """Stage an event in the caller's transaction; it is relayed only if that transaction commits."""
    await session.execute(insert(table).values(**outbox_fields(envelope)))


class SqlOutboxStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], table: Table) -> None:
        self._session_factory = session_factory
        self._table = table

    async def claim_batch(self, *, limit: int, lease: timedelta) -> list[OutboxMessage]:
        t = self._table
        now = datetime.now(UTC)
        due = (
            select(t.c.event_id)
            .where(t.c.status == STATUS_PENDING, t.c.available_at <= now)
            .order_by(t.c.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
            .scalar_subquery()
        )
        stmt = (
            update(t)
            .where(t.c.event_id.in_(due))
            .values(available_at=now + lease)
            .returning(t.c.event_id, t.c.subject, t.c.body, t.c.attempts, t.c.created_at)
        )
        async with self._session_factory() as session, session.begin():
            rows = (await session.execute(stmt)).all()
        rows.sort(key=lambda row: row.created_at)
        return [
            OutboxMessage(event_id=r.event_id, subject=r.subject, body=r.body, attempts=r.attempts)
            for r in rows
        ]

    async def mark_published(self, event_id: str) -> None:
        t = self._table
        async with self._session_factory() as session, session.begin():
            await session.execute(
                update(t)
                .where(t.c.event_id == event_id)
                .values(status=STATUS_PUBLISHED, published_at=datetime.now(UTC), last_error=None)
            )

    async def mark_failed(self, event_id: str, *, error: str, retry_at: datetime) -> None:
        t = self._table
        async with self._session_factory() as session, session.begin():
            await session.execute(
                update(t)
                .where(t.c.event_id == event_id)
                .values(attempts=t.c.attempts + 1, last_error=error, available_at=retry_at)
            )

    async def pending_count(self) -> int:
        t = self._table
        async with self._session_factory() as session:
            return int(
                await session.scalar(select(func.count()).select_from(t).where(t.c.status == STATUS_PENDING))
                or 0
            )
