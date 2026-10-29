"""Who may see and act on an appointment (ABAC over provider-service facts, on top of RBAC permissions).

- customer: the appointment's ``user_id``;
- provider: the owner (``user_id``) of the appointment's provider in provider-service;
- facility: a ``facility_admin`` or ``scheduler`` of the appointment's facility (``billing`` is not enough);
- platform: holders of ``appointments:manage`` (tenant-wide operations staff).
Tenant isolation is applied by every query (``tenant_id`` of the caller), before any of these checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from healuxa_py_common.events.envelope import EventActor
from healuxa_py_common.middleware.auth import Principal

from appointment_service.clients.provider_directory import ProviderDirectory, ProviderUnavailable
from appointment_service.domain.errors import unavailable
from appointment_service.infra.models import Appointment

MANAGE_PERMISSION = "appointments:manage"
SCHEDULING_ROLES = frozenset({"facility_admin", "scheduler"})


@dataclass(frozen=True)
class Access:
    principal: Principal
    provider_ids: frozenset[str] = field(default_factory=frozenset)
    scheduling_facilities: frozenset[str] = field(default_factory=frozenset)

    @property
    def is_manager(self) -> bool:
        return MANAGE_PERMISSION in self.principal.permissions

    @property
    def has_staff_scope(self) -> bool:
        return self.is_manager or bool(self.provider_ids) or bool(self.scheduling_facilities)

    def is_customer(self, appointment: Appointment) -> bool:
        return appointment.user_id == self.principal.user_id

    def staff_party(self, appointment: Appointment) -> str | None:
        """The capacity in which the caller acts for the practice, if any."""
        if appointment.provider_id in self.provider_ids:
            return "provider"
        if appointment.facility_id in self.scheduling_facilities:
            return "facility"
        if self.is_manager:
            return "platform"
        return None

    def can_view(self, appointment: Appointment) -> bool:
        return self.is_customer(appointment) or self.staff_party(appointment) is not None

    def actor(self) -> EventActor:
        return EventActor(type="user", id=self.principal.user_id)


def is_manager(principal: Principal) -> bool:
    return MANAGE_PERMISSION in principal.permissions


async def load_access(directory: ProviderDirectory, principal: Principal) -> Access:
    """Resolve the caller's practice relationships from provider-service (fails closed with 503)."""
    try:
        actor = await directory.actor(principal.tenant_id, principal.user_id)
    except ProviderUnavailable as exc:
        raise unavailable() from exc
    return Access(
        principal=principal,
        provider_ids=frozenset(actor.provider_ids),
        scheduling_facilities=frozenset(r.facility_id for r in actor.facility_roles if r.role in SCHEDULING_ROLES),
    )


async def access_for(directory: ProviderDirectory, principal: Principal, appointment: Appointment) -> Access:
    """Customers acting on their own appointment need no remote lookup."""
    if appointment.user_id == principal.user_id:
        return Access(principal=principal)
    return await load_access(directory, principal)
