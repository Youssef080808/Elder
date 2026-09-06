"""Delegation rules, as pure predicates.

For when the elder can no longer manage their own account. The point is not
to hand someone the keys; it is that the elder's control does not vanish when
they stop using the app -- it becomes something the whole family can watch
being exercised on their behalf.

Why the proxy does not simply get everything: financial exploitation of elders
is overwhelmingly committed by family members. A one-toggle "give a relative
everything, including the money" path would build the exact shape of the
problem this app exists to reduce, so `finances` is excluded from every preset
for a proxy and has to be granted deliberately, one toggle, by the elder.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import FrozenSet, Optional

from app.config import PROXY_TERM_DAYS
from app.domain.categories import DataCategory, Preset, preset_grants


class ProxyViolation(Exception):
    """Raised when an action breaks a delegation rule. Routes turn this into a
    403 -- the rule is enforced on the server, never by hiding a button."""


def is_active_proxy(person, now: Optional[datetime] = None) -> bool:
    """Delegation is time-bounded by default: an expired proxy keeps their own
    permission column but loses the authority to act for the elder."""
    if person is None or not getattr(person, "is_proxy", False):
        return False
    expires = getattr(person, "proxy_expires_at", None)
    if expires is None:
        return True
    return (now or datetime.utcnow()) < expires


def default_expiry(now: Optional[datetime] = None) -> datetime:
    return (now or datetime.utcnow()) + timedelta(days=PROXY_TERM_DAYS)


def proxy_initial_grants() -> FrozenSet[DataCategory]:
    """The widest preset, minus finances."""
    return frozenset(preset_grants(Preset.CLOSE_FAMILY)) - {DataCategory.FINANCES}


def preset_grants_for(target, preset: Preset, now: Optional[datetime] = None) -> FrozenSet[DataCategory]:
    """Stamping a preset onto the active proxy never includes finances.

    Otherwise "close family" would be a single click that hands the person
    managing the elder's consent their money as well.
    """
    grants = frozenset(preset_grants(preset))
    if is_active_proxy(target, now):
        grants = grants - {DataCategory.FINANCES}
    return grants


def assert_can_edit_column(actor, target, now: Optional[datetime] = None) -> bool:
    """Returns True when the actor is acting as proxy (for logging).

    The elder may edit anyone's column. An active proxy may edit anyone's
    column except their own -- the one who administers consent may not widen
    their own access.
    """
    if actor is None:
        raise ProxyViolation("Not signed in.")
    if getattr(actor, "role", None) == "elder":
        return False
    if not is_active_proxy(actor, now):
        raise ProxyViolation(
            "Only {} or an active proxy can change who sees what.".format(
                getattr(actor, "name", "the elder")
            )
        )
    if target is not None and target.id == actor.id:
        raise ProxyViolation(
            "A proxy cannot change their own access. Ask another family member "
            "or the elder to make this change."
        )
    return True


def assert_can_appoint(actor, now: Optional[datetime] = None) -> None:
    """Only the elder appoints a proxy. A proxy cannot appoint another proxy;
    delegation does not become self-propagating."""
    if actor is None or getattr(actor, "role", None) != "elder":
        raise ProxyViolation(
            "Only the elder can appoint or revoke a proxy. A proxy cannot "
            "appoint another proxy."
        )


def assert_can_be_proxy(target) -> None:
    if target is None:
        raise ProxyViolation("No such person.")
    if getattr(target, "role", None) == "elder":
        raise ProxyViolation("The elder cannot be their own proxy.")
