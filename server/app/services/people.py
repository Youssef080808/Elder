"""Lookups for the elder and the circle of people around them."""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.categories import Preset
from app.models import Person, PreferenceRecord
from app.domain.preferences import Preferences


def get_person(db: Session, person_id: Optional[str]) -> Optional[Person]:
    if not person_id:
        return None
    return db.get(Person, person_id)


def the_elder(db: Session) -> Person:
    """This build supports one elder per deployment. The models carry elder_id
    throughout so that stays a seeding decision, not an architectural one."""
    elder = db.execute(select(Person).where(Person.role == "elder")).scalars().first()
    if elder is None:  # pragma: no cover - only reachable on an unseeded db
        raise LookupError("No elder in the database. Run the seed.")
    return elder


def circle(db: Session, elder_id: str) -> List[Person]:
    """Everyone with a permission column: family and caregivers, not the elder."""
    people = db.execute(
        select(Person).where(Person.elder_id == elder_id, Person.role != "elder")
    ).scalars().all()
    return sorted(people, key=lambda p: (p.role != "family", p.name))


def load_preferences(db: Session, elder_id: str) -> Preferences:
    record = db.execute(
        select(PreferenceRecord).where(PreferenceRecord.elder_id == elder_id)
    ).scalars().first()
    return Preferences.from_dict(record.data if record else None)


def save_preferences(db: Session, elder_id: str, prefs: Preferences) -> None:
    record = db.execute(
        select(PreferenceRecord).where(PreferenceRecord.elder_id == elder_id)
    ).scalars().first()
    if record is None:
        record = PreferenceRecord(elder_id=elder_id, data=prefs.to_dict())
        db.add(record)
    else:
        record.data = prefs.to_dict()
    db.commit()


def add_person(
    db: Session,
    *,
    elder: Person,
    actor: Person,
    name: str,
    role: str,
    gender: str,
    relation_label: str,
    preset: Preset,
) -> Person:
    """Add someone to the circle and stamp one preset into *their* column.

    The preset is a starting point, not a category of person: from this moment
    the values are theirs and diverge freely.
    """
    from app.services.consent import apply_preset, ensure_permission_rows

    person = Person(
        name=name.strip() or "Unnamed",
        role=role if role in ("family", "caregiver") else "caregiver",
        gender=gender if gender in ("female", "male") else "unspecified",
        relation_label=relation_label.strip(),
        elder_id=elder.id,
    )
    db.add(person)
    db.flush()
    ensure_permission_rows(db, person)
    db.commit()
    return apply_preset(db, elder_id=elder.id, actor=actor, target=person, preset=preset)
