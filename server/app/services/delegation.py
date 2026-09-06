"""Appointing and revoking a proxy."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import PROXY_TERM_DAYS
from app.domain.categories import DataCategory
from app.domain.proxy import (
    assert_can_appoint,
    assert_can_be_proxy,
    default_expiry,
    is_active_proxy,
    proxy_initial_grants,
)
from app.domain.logbook import LogEntryKind
from app.models import Permission, Person
from app.services import activity
from app.services.consent import ensure_permission_rows


def appoint_proxy(db: Session, *, elder: Person, actor: Person, target: Person) -> Person:
    """The elder appoints. Appointing a new proxy revokes the previous one, so
    there is never more than one at a time."""
    assert_can_appoint(actor)
    assert_can_be_proxy(target)

    previous: Optional[Person] = None
    for person in db.execute(
        select(Person).where(Person.elder_id == elder.id, Person.is_proxy.is_(True))
    ).scalars().all():
        if person.id == target.id:
            continue
        person.is_proxy = False
        person.proxy_expires_at = None
        previous = person

    target.is_proxy = True
    target.proxy_expires_at = default_expiry()
    ensure_permission_rows(db, target)

    grants = proxy_initial_grants()
    rows = db.execute(select(Permission).where(Permission.person_id == target.id)).scalars().all()
    for row in rows:
        if DataCategory(row.category) in grants:
            row.granted = True
        elif DataCategory(row.category) is DataCategory.FINANCES:
            row.granted = False  # never by default, never by preset
    db.flush()

    if previous is not None:
        activity.record(
            db,
            elder_id=elder.id,
            actor=actor,
            kind=LogEntryKind.PROXY,
            action="{} ended {}'s role as proxy".format(actor.name, previous.name),
            detail="Appointing a new proxy revokes the previous one.",
            icon="D",
            target_person_id=previous.id,
            commit=False,
        )
    activity.record(
        db,
        elder_id=elder.id,
        actor=actor,
        kind=LogEntryKind.PROXY,
        action="{} appointed {} as proxy".format(actor.name, target.name),
        detail=(
            "Widest access except finances, which stays off until granted "
            "separately. Expires in {} days and can be revoked at any time.".format(
                PROXY_TERM_DAYS
            )
        ),
        icon="D",
        target_person_id=target.id,
        categories=list(grants),
        commit=False,
    )
    db.commit()
    db.refresh(target)
    return target


def revoke_proxy(db: Session, *, elder: Person, actor: Person) -> Optional[Person]:
    """Revocable at any time. Their own permission column survives; only the
    authority to act on the elder's behalf ends."""
    assert_can_appoint(actor)
    current = db.execute(
        select(Person).where(Person.elder_id == elder.id, Person.is_proxy.is_(True))
    ).scalars().first()
    if current is None:
        return None
    current.is_proxy = False
    current.proxy_expires_at = None
    db.flush()
    activity.record(
        db,
        elder_id=elder.id,
        actor=actor,
        kind=LogEntryKind.PROXY,
        action="{} revoked {}'s proxy role".format(actor.name, current.name),
        detail="Their own access is unchanged; they can no longer act for {}.".format(elder.name),
        icon="D",
        target_person_id=current.id,
        commit=False,
    )
    db.commit()
    return current


def proxy_status(db: Session, elder_id: str):
    """(person, expires_at) for the active proxy, or (None, None)."""
    for person in db.execute(
        select(Person).where(Person.elder_id == elder_id, Person.is_proxy.is_(True))
    ).scalars().all():
        if is_active_proxy(person):
            return person, person.proxy_expires_at
    return None, None


def days_remaining(expires_at: Optional[datetime]) -> Optional[int]:
    if expires_at is None:
        return None
    return max(0, (expires_at - datetime.utcnow()).days)
