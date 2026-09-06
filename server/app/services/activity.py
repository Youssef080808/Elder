"""Writing and reading the activity log.

The log is not the consent design -- the grid is. If answering "did the elder
agree to this?" required reading history, consent would have no architecture.
The log answers a different question: what actually happened, including what
was *shown* to whom, which is the part an elder normally never gets to see.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.categories import CATEGORY_LABELS, DataCategory
from app.domain.logbook import LogEntryKind
from app.models import LogEntry, Person


def _next_seq(db: Session, elder_id: str) -> int:
    rows = db.execute(
        select(LogEntry.sort_seq).where(LogEntry.elder_id == elder_id)
    ).scalars().all()
    return (max(rows) + 1) if rows else 1


def record(
    db: Session,
    *,
    elder_id: str,
    actor: Person,
    action: str,
    kind: str = LogEntryKind.CARE,
    detail: str = "",
    target_person_id: Optional[str] = None,
    acting_as_proxy: bool = False,
    categories: Iterable[DataCategory] = (),
    icon: str = "V",
    commit: bool = True,
) -> LogEntry:
    entry = LogEntry(
        elder_id=elder_id,
        actor_id=actor.id,
        acting_as_proxy=acting_as_proxy,
        kind=kind,
        action=action,
        detail=detail,
        target_person_id=target_person_id,
        icon=icon,
        timestamp=datetime.utcnow(),
        categories=",".join(sorted(c.value for c in categories)),
        sort_seq=_next_seq(db, elder_id),
    )
    db.add(entry)
    if commit:
        db.commit()
    return entry


def record_disclosure(
    db: Session,
    *,
    elder_id: str,
    viewer: Person,
    surface_label: str,
    categories: Iterable[DataCategory],
) -> Optional[LogEntry]:
    """Log what a person was shown -- but collapse repeats.

    Permissions are re-checked on every page load, so a caregiver refreshing a
    shift card would otherwise bury the elder's log. A new row is written only
    when the disclosed set actually changes, which means a revocation shows up
    in the log as a visible narrowing.
    """
    cats = sorted({c.value for c in categories})
    signature = ",".join(cats)
    previous = db.execute(
        select(LogEntry)
        .where(
            LogEntry.elder_id == elder_id,
            LogEntry.actor_id == viewer.id,
            LogEntry.kind == LogEntryKind.DISCLOSURE,
            LogEntry.detail == surface_label,
        )
        .order_by(LogEntry.sort_seq.desc())
    ).scalars().first()
    if previous is not None and (previous.categories or "") == signature:
        return None

    shown = ", ".join(CATEGORY_LABELS[DataCategory(c)].lower() for c in cats) or "nothing"
    return record(
        db,
        elder_id=elder_id,
        actor=viewer,
        kind=LogEntryKind.DISCLOSURE,
        action="{} was shown {}".format(viewer.name, shown),
        detail=surface_label,
        icon="V",
        categories=[DataCategory(c) for c in cats],
    )


@dataclass
class ActivityRow:
    when: datetime
    actor_name: str
    text: str
    detail: str
    kind: str
    icon: str
    acting_as_proxy: bool
    categories: List[str]

    def to_dict(self) -> dict:
        return {
            "who": self.actor_name,
            "text": self.text,
            "detail": self.detail,
            "time": self.when.isoformat(timespec="seconds"),
            "kind": self.kind,
            "icon": self.icon,
            "proxy": self.acting_as_proxy,
            "categories": self.categories,
        }

    @property
    def is_disclosure(self) -> bool:
        return self.kind == LogEntryKind.DISCLOSURE


def _visible_to(entry: LogEntry, viewer: Person) -> bool:
    if viewer.role == "elder":
        return True
    # Proxy actions are visible to every family member. Visibility to the
    # family is the safeguard on delegation, not restriction of the proxy.
    if entry.acting_as_proxy and viewer.role == "family":
        return True
    if entry.kind in (LogEntryKind.PROXY, LogEntryKind.CONSENT) and viewer.role == "family":
        return True
    return entry.actor_id == viewer.id or entry.target_person_id == viewer.id


def activity_for(db: Session, elder_id: str, viewer: Person, limit: int = 60) -> List[ActivityRow]:
    entries = db.execute(
        select(LogEntry)
        .where(LogEntry.elder_id == elder_id)
        .order_by(LogEntry.sort_seq.desc())
    ).scalars().all()

    names = {p.id: p.name for p in db.execute(select(Person)).scalars().all()}
    rows: List[ActivityRow] = []
    for entry in entries:
        if not _visible_to(entry, viewer):
            continue
        text = entry.action
        if entry.acting_as_proxy:
            actor_name = names.get(entry.actor_id, "Someone")
            text = "{}, acting as proxy, {}".format(actor_name, _strip_actor(entry.action, actor_name))
        rows.append(
            ActivityRow(
                when=entry.timestamp,
                actor_name=names.get(entry.actor_id, "Someone"),
                text=text,
                detail=entry.detail or "",
                kind=entry.kind,
                icon=entry.icon or "V",
                acting_as_proxy=entry.acting_as_proxy,
                categories=[c for c in (entry.categories or "").split(",") if c],
            )
        )
        if len(rows) >= limit:
            break
    return rows


def _strip_actor(action: str, actor_name: str) -> str:
    """"Amira changed X" -> "changed X", so the proxy phrasing reads cleanly."""
    prefix = actor_name + " "
    return action[len(prefix):] if action.startswith(prefix) else action
