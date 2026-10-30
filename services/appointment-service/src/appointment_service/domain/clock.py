"""Single source of 'now' for booking rules, so time-dependent behaviour is testable."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


class Clock:
    def __init__(self) -> None:
        self._frozen: datetime | None = None

    def now(self) -> datetime:
        return self._frozen if self._frozen is not None else datetime.now(UTC)

    # Test support -------------------------------------------------------------------------------
    def freeze(self, at: datetime) -> None:
        self._frozen = at.astimezone(UTC)

    def travel(self, delta: timedelta) -> None:
        self._frozen = self.now() + delta

    def reset(self) -> None:
        self._frozen = None


clock = Clock()
