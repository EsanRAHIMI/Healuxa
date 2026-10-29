"""Concierge case state machine: which transitions exist and which role may perform them.

    submitted → triaged → assigned → in_progress ⇄ awaiting_customer → arranged → completed
    (any open state) → cancelled | escalated;  escalated → back to work (supervisor only)

``assigned`` is entered only through the assignment endpoint and ``escalated`` only through the
escalation endpoint, so their side effects (assignee, escalated_from) are always recorded.
"""

from __future__ import annotations

from healuxa_py_common.errors import ApiError

TERMINAL = frozenset({"completed", "cancelled"})
OPEN = frozenset({"submitted", "triaged", "assigned", "in_progress", "awaiting_customer", "arranged", "escalated"})

TRANSITIONS: dict[str, frozenset[str]] = {
    "submitted": frozenset({"triaged", "assigned", "cancelled", "escalated"}),
    "triaged": frozenset({"assigned", "cancelled", "escalated"}),
    "assigned": frozenset({"in_progress", "cancelled", "escalated"}),
    "in_progress": frozenset({"awaiting_customer", "arranged", "cancelled", "escalated"}),
    "awaiting_customer": frozenset({"in_progress", "arranged", "cancelled", "escalated"}),
    "arranged": frozenset({"completed", "in_progress", "cancelled", "escalated"}),
    "escalated": frozenset({"triaged", "assigned", "in_progress", "awaiting_customer", "arranged", "cancelled"}),
    "completed": frozenset(),
    "cancelled": frozenset(),
}

# Targets reachable through the generic transitions endpoint.
DIRECT_TARGETS = frozenset({"triaged", "in_progress", "awaiting_customer", "arranged", "completed", "cancelled"})
# States in which a (re)assignment moves the case to ``assigned``.
ASSIGNABLE_INTO_ASSIGNED = frozenset({"submitted", "triaged"})


def illegal(from_status: str, to_status: str) -> ApiError:
    return ApiError(
        status=409,
        code="conflict",
        title="Illegal transition",
        detail=f"Cannot move a case from {from_status} to {to_status}",
    )


def can_transition(from_status: str, to_status: str) -> bool:
    return to_status in TRANSITIONS.get(from_status, frozenset())


def ensure_transition(from_status: str, to_status: str) -> None:
    if not can_transition(from_status, to_status):
        raise illegal(from_status, to_status)


def role_may_transition(role: str, *, from_status: str, to_status: str, is_assignee: bool) -> bool:
    """Role rules on top of the graph. ``role`` is customer | coordinator | supervisor."""
    if role == "supervisor":
        return True
    if from_status == "escalated":
        return False  # only a supervisor resolves an escalation
    if role == "customer":
        return to_status == "cancelled"
    if role == "coordinator":
        if to_status == "triaged":
            return True  # any tenant coordinator may triage the incoming queue
        return is_assignee
    return False
