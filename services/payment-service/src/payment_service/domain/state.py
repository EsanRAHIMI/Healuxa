"""Payment state machine. Monotonic: processor events that arrive late or out of order can never move a
payment backwards (e.g. an old ``payment_failed`` after ``succeeded`` is ignored)."""

from __future__ import annotations

from datetime import datetime

CAPTURED_FAMILY = {"succeeded", "partially_refunded", "refunded"}
TERMINAL = {"canceled", *CAPTURED_FAMILY}

# status -> statuses reachable from it via processor events/commands
TRANSITIONS: dict[str, set[str]] = {
    "pending": {"processing", "authorized", "succeeded", "failed", "canceled"},
    "processing": {"authorized", "succeeded", "failed", "canceled"},
    "failed": {"pending", "processing", "authorized", "succeeded", "canceled"},
    "authorized": {"succeeded", "canceled"},
    "succeeded": {"partially_refunded", "refunded"},
    "partially_refunded": {"partially_refunded", "refunded"},
    "refunded": set(),
    "canceled": set(),
}

# Transitions that go "sideways/backwards" in progress order are only accepted from a newer event.
_RANK = {"pending": 0, "failed": 0, "processing": 1, "authorized": 2, "succeeded": 3, "partially_refunded": 3, "refunded": 3, "canceled": 3}


class IllegalTransition(Exception):
    def __init__(self, current: str, target: str) -> None:
        super().__init__(f"illegal payment transition {current} -> {target}")
        self.current = current
        self.target = target


def can_transition(current: str, target: str) -> bool:
    return target in TRANSITIONS.get(current, set())


def require_transition(current: str, target: str) -> None:
    if not can_transition(current, target):
        raise IllegalTransition(current, target)


def should_apply(current: str, target: str, *, event_at: datetime | None, last_event_at: datetime | None) -> bool:
    """Decide whether a processor-reported status should be applied."""
    if current == target or not can_transition(current, target):
        return False
    if _RANK[target] > _RANK[current]:
        return True
    # Same or lower rank (e.g. processing -> failed, failed -> pending): only if not older than what we applied.
    return event_at is None or last_event_at is None or event_at >= last_event_at
