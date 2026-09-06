"""The coming week's coverage.

Gaps are the point. A group chat cannot show that nobody is covering Thursday;
it can only show that nobody replied about Thursday, which is not the same
information and cannot be acted on.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as Date
from datetime import timedelta
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.preferences import check_bathing_assignment, minutes
from app.models import Person, Shift
from app.services.people import load_preferences


@dataclass
class ShiftRow:
    shift: Shift
    caregiver_name: str
    mine: bool
    warning: str = ""


@dataclass
class DayRow:
    day: Date
    label: str
    weekday: str
    shifts: List[ShiftRow] = field(default_factory=list)
    #: Shifts that exist on the schedule with nobody on them. Always shown to
    #: everyone: that a slot is unstaffed is a fact about the elder, not
    #: information about a colleague.
    open_shifts: List[Shift] = field(default_factory=list)
    #: Covered shifts this viewer is not entitled to see by name.
    hidden_count: int = 0

    @property
    def is_gap(self) -> bool:
        """Nobody at all is coming today."""
        return not self.shifts and self.hidden_count == 0

    @property
    def needs_attention(self) -> bool:
        return self.is_gap or bool(self.open_shifts)

    @property
    def has_warning(self) -> bool:
        return any(s.warning for s in self.shifts)


@dataclass
class Coverage:
    days: List[DayRow]
    sees_everything: bool
    gap_count: int
    open_shift_count: int
    warning_count: int

    @property
    def uncovered_day_count(self) -> int:
        return sum(1 for day in self.days if day.needs_attention)


def week_coverage(
    db: Session, *, elder: Person, viewer: Person, today: Optional[Date] = None, days: int = 7
) -> Coverage:
    """Family members see every row. A paid caregiver sees only their own
    shifts -- the schedule of the other people in someone's home is not theirs
    to browse -- but still sees that a day is unstaffed, because that is a
    fact about the elder, not about a colleague."""
    today = today or Date.today()
    sees_everything = viewer.role in ("family", "elder")
    prefs = load_preferences(db, elder.id)

    window = [today + timedelta(days=i) for i in range(days)]
    shifts = db.execute(
        select(Shift)
        .where(Shift.elder_id == elder.id, Shift.date >= window[0], Shift.date <= window[-1])
        .order_by(Shift.date, Shift.start)
    ).scalars().all()
    people = {p.id: p for p in db.execute(select(Person)).scalars().all()}

    rows: List[DayRow] = []
    for day in window:
        day_row = DayRow(day=day, label=_label(day, today), weekday=day.strftime("%A"))
        day_row.open_shifts = [
            s for s in shifts if s.date == day and not (s.covered and s.caregiver_id)
        ]
        for shift in [s for s in shifts if s.date == day and s.covered and s.caregiver_id]:
            caregiver = people.get(shift.caregiver_id)
            mine = shift.caregiver_id == viewer.id
            if not sees_everything and not mine:
                day_row.hidden_count += 1
                continue
            check = check_bathing_assignment(
                prefs, caregiver.gender if caregiver else None, bool(shift.includes_personal_care)
            )
            day_row.shifts.append(
                ShiftRow(
                    shift=shift,
                    caregiver_name=caregiver.name if caregiver else "Unassigned",
                    mine=mine,
                    warning="" if check.ok else check.warning,
                )
            )
        rows.append(day_row)

    return Coverage(
        days=rows,
        sees_everything=sees_everything,
        gap_count=sum(1 for r in rows if r.is_gap),
        open_shift_count=sum(len(r.open_shifts) for r in rows),
        warning_count=sum(1 for r in rows for s in r.shifts if s.warning),
    )


def shifts_for(db: Session, *, caregiver: Person, today: Optional[Date] = None) -> List[Shift]:
    today = today or Date.today()
    return db.execute(
        select(Shift)
        .where(Shift.caregiver_id == caregiver.id, Shift.date >= today)
        .order_by(Shift.date, Shift.start)
    ).scalars().all()


def current_shift(db: Session, *, caregiver: Person, today: Optional[Date] = None) -> Optional[Shift]:
    """The shift to push. Today's if there is one, otherwise the next."""
    upcoming = shifts_for(db, caregiver=caregiver, today=today)
    return upcoming[0] if upcoming else None


def _label(day: Date, today: Date) -> str:
    delta = (day - today).days
    if delta == 0:
        return "Today"
    if delta == 1:
        return "Tomorrow"
    return day.strftime("%a %-d %b")


def uncovered_shifts(db: Session, *, elder_id: str, today: Optional[Date] = None) -> List[Shift]:
    """Gaps in the coming week, offered when a new caregiver is added so that
    adding a person can close a gap in the same step."""
    today = today or Date.today()
    return db.execute(
        select(Shift)
        .where(Shift.elder_id == elder_id, Shift.date >= today, Shift.covered.is_(False))
        .order_by(Shift.date, Shift.start)
    ).scalars().all()


def assign_shifts(db: Session, *, caregiver: Person, shift_ids: List[str]) -> int:
    assigned = 0
    for shift_id in shift_ids:
        shift = db.get(Shift, shift_id)
        if shift is None or shift.covered:
            continue
        shift.caregiver_id = caregiver.id
        shift.covered = True
        assigned += 1
    db.flush()
    return assigned


def shift_by_id(db: Session, *, shift_id: str, caregiver: Person) -> Optional[Shift]:
    """A caregiver may only open their own shift. This is an ownership check,
    separate from and prior to the two visibility filters."""
    shift = db.get(Shift, shift_id)
    if shift is None:
        return None
    if caregiver.role == "elder":
        return shift
    return shift if shift.caregiver_id == caregiver.id else None


def workload(db: Session, *, elder: Person, today: Optional[Date] = None, days: int = 7):
    """Hours and shifts per person over the coming week.

    Scheduling arithmetic only. It never reaches into a category, which is why
    it does not need to pass through the permission engine -- and why a change
    here can never become a leak.
    """
    today = today or Date.today()
    window_end = today + timedelta(days=days - 1)
    shifts = db.execute(
        select(Shift).where(
            Shift.elder_id == elder.id,
            Shift.date >= today,
            Shift.date <= window_end,
            Shift.covered.is_(True),
        )
    ).scalars().all()

    people = {
        p.id: p
        for p in db.execute(
            select(Person).where(Person.elder_id == elder.id, Person.role != "elder")
        ).scalars().all()
    }
    totals = {pid: {"hours": 0, "shifts": 0} for pid in people}
    for shift in shifts:
        if shift.caregiver_id not in totals:
            continue
        totals[shift.caregiver_id]["hours"] += max(
            0, (minutes(shift.end) - minutes(shift.start)) // 60
        )
        totals[shift.caregiver_id]["shifts"] += 1

    rows = []
    for pid, person in people.items():
        rows.append(
            {
                "id": person.id,
                "name": person.name,
                "role_label": person.role_label,
                "initials": person.initials,
                "tone": person.tone,
                "hours": totals[pid]["hours"],
                "shifts": totals[pid]["shifts"],
            }
        )
    rows.sort(key=lambda r: (-r["hours"], r["name"]))
    return rows


def to_dict(week: Coverage) -> dict:
    return {
        "sees_everything": week.sees_everything,
        "gap_count": week.gap_count,
        "open_shift_count": week.open_shift_count,
        "warning_count": week.warning_count,
        "uncovered_day_count": week.uncovered_day_count,
        "days": [
            {
                "date": day.day.isoformat(),
                "label": day.label,
                "weekday": day.weekday,
                "is_gap": day.is_gap,
                "needs_attention": day.needs_attention,
                "hidden_count": day.hidden_count,
                "open_shifts": [
                    {"id": s.id, "start": s.start, "end": s.end, "label": s.label}
                    for s in day.open_shifts
                ],
                "shifts": [
                    {
                        "id": row.shift.id,
                        "start": row.shift.start,
                        "end": row.shift.end,
                        "label": row.shift.label,
                        "caregiver_name": row.caregiver_name,
                        "mine": row.mine,
                        "warning": row.warning,
                    }
                    for row in day.shifts
                ],
            }
            for day in week.days
        ],
    }
