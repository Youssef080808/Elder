"""The permission grid: reading it, and the only two ways to change it.

Granular, legible, revocable. There is no global "share everything" state in
this module because there is none in the product: the only writes available
are `set_permission` (one person, one category) and `apply_preset` (one
person, a set of categories stamped into their column and immediately theirs).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.categories import (
    CATEGORY_BLURBS,
    CATEGORY_LABELS,
    CATEGORY_ORDER,
    DIGNITY_SENSITIVE,
    DataCategory,
    Preset,
    PRESET_LABELS,
)
from app.domain.permissions import has_permission
from app.domain.proxy import assert_can_edit_column, is_active_proxy, preset_grants_for
from app.domain.logbook import LogEntryKind
from app.models import Permission, Person
from app.services import activity


@dataclass
class GridCell:
    category: DataCategory
    granted: bool
    locked: bool = False        # actor may not change this cell
    lock_reason: str = ""


@dataclass
class GridColumn:
    person: Person
    cells: List[GridCell]
    is_proxy: bool
    granted_count: int


@dataclass
class Grid:
    categories: List[DataCategory]
    labels: Dict[str, str]
    blurbs: Dict[str, str]
    columns: List[GridColumn]
    dignity_sensitive: List[str]


def ensure_permission_rows(db: Session, person: Person) -> None:
    """Every person carries one row per category, granted or not. An absent
    row and a denied row must never mean different things.

    Reads the table rather than `person.permissions`: the relationship can be
    a stale snapshot taken before these rows existed, and inserting a
    duplicate column is exactly the kind of quiet corruption that would make
    the grid untrustworthy.
    """
    existing = set(
        db.execute(
            select(Permission.category).where(Permission.person_id == person.id)
        ).scalars().all()
    )
    missing = [c for c in CATEGORY_ORDER if c.value not in existing]
    if not missing:
        return
    for category in missing:
        db.add(Permission(person_id=person.id, category=category.value, granted=False))
    db.flush()
    db.refresh(person)


def build_grid(db: Session, people: List[Person], actor: Person) -> Grid:
    columns: List[GridColumn] = []
    for person in people:
        cells: List[GridCell] = []
        for category in CATEGORY_ORDER:
            locked, reason = _cell_lock(actor, person, category)
            cells.append(
                GridCell(
                    category=category,
                    granted=has_permission(person, category),
                    locked=locked,
                    lock_reason=reason,
                )
            )
        columns.append(
            GridColumn(
                person=person,
                cells=cells,
                is_proxy=is_active_proxy(person),
                granted_count=sum(1 for c in cells if c.granted),
            )
        )
    return Grid(
        categories=list(CATEGORY_ORDER),
        labels={c.value: CATEGORY_LABELS[c] for c in CATEGORY_ORDER},
        blurbs={c.value: CATEGORY_BLURBS[c] for c in CATEGORY_ORDER},
        columns=columns,
        dignity_sensitive=[c.value for c in DIGNITY_SENSITIVE],
    )


def _cell_lock(actor: Person, target: Person, category: DataCategory):
    """UI hinting only. Every one of these is re-checked server-side on write."""
    if actor.role == "elder":
        return False, ""
    if is_active_proxy(actor) and target.id == actor.id:
        return True, "A proxy cannot change their own access."
    if is_active_proxy(actor):
        return False, ""
    return True, "Only the elder or an active proxy can change this."


def set_permission(
    db: Session,
    *,
    elder_id: str,
    actor: Person,
    target: Person,
    category: DataCategory,
    granted: bool,
) -> Person:
    """One person, one category. Enforced server-side, not by hiding the UI."""
    as_proxy = assert_can_edit_column(actor, target)
    ensure_permission_rows(db, target)

    row = db.execute(
        select(Permission).where(
            Permission.person_id == target.id, Permission.category == category.value
        )
    ).scalars().first()
    if row is None:  # pragma: no cover - ensure_permission_rows just made it
        row = Permission(person_id=target.id, category=category.value, granted=False)
        db.add(row)

    if row.granted != granted:
        row.granted = granted
        db.flush()
        verb = "gave" if granted else "removed"
        preposition = "access to" if granted else "access to"
        activity.record(
            db,
            elder_id=elder_id,
            actor=actor,
            kind=LogEntryKind.CONSENT,
            acting_as_proxy=as_proxy,
            action="{} {} {} {} {}".format(
                actor.name, verb, target.name, preposition, CATEGORY_LABELS[category].lower()
            ),
            detail=_finance_note(target, category, granted),
            icon="P",
            target_person_id=target.id,
            categories=[category],
            commit=False,
        )
    db.commit()
    db.refresh(target)
    return target


def apply_preset(
    db: Session, *, elder_id: str, actor: Person, target: Person, preset: Preset
) -> Person:
    """Stamp a set of values into one person's column.

    After stamping they are that person's values and diverge freely: editing
    Fatima's column never touches another caregiver's.
    """
    as_proxy = assert_can_edit_column(actor, target)
    ensure_permission_rows(db, target)

    grants = preset_grants_for(target, preset)
    rows = db.execute(
        select(Permission).where(Permission.person_id == target.id)
    ).scalars().all()
    for row in rows:
        row.granted = DataCategory(row.category) in grants
    db.flush()

    detail = ""
    if is_active_proxy(target) and DataCategory.FINANCES not in grants:
        detail = (
            "Finances stayed off: presets never grant money access to a proxy. "
            "It has to be granted on its own."
        )
    activity.record(
        db,
        elder_id=elder_id,
        actor=actor,
        kind=LogEntryKind.CONSENT,
        acting_as_proxy=as_proxy,
        action="{} applied the {} preset to {}".format(
            actor.name, PRESET_LABELS[preset].lower(), target.name
        ),
        detail=detail,
        icon="P",
        target_person_id=target.id,
        categories=list(grants),
        commit=False,
    )
    db.commit()
    db.refresh(target)
    return target


def _finance_note(target: Person, category: DataCategory, granted: bool) -> str:
    if category is DataCategory.FINANCES and granted:
        if is_active_proxy(target):
            return "Deliberate, separate grant of financial access to the proxy."
        return "Financial access granted."
    return ""
