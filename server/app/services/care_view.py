"""Assembling what a caregiver is shown for one shift.

This module is the reason no route handler queries a category table. It takes
(viewer, shift) and returns a view object that *only ever contains* data the
viewer passed both filters for. The template cannot leak what it was never
given, and the client never receives the elder's full record to filter in
JavaScript.

The card is pushed, not searched. A caregiver arriving at 6am does not know
what to ask for -- not knowing what you don't know is the actual handoff
failure -- so the card leads with prayer, medication, diet, language and last
night's note without anyone having to look them up.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import FrozenSet, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.categories import CATEGORY_LABELS, DIGNITY_SENSITIVE, DataCategory
from app.domain.permissions import (
    RelevanceContext,
    Surface,
    visible_categories,
    withheld_as_irrelevant,
)
from app.domain.preferences import (
    GENDER_LABELS,
    MEAT_LABELS,
    Preferences,
    apply_prayer_buffer,
    check_bathing_assignment,
    minutes,
)
from app.domain.logbook import LogEntryKind
from app.models import (
    Appointment,
    CareNote,
    HandoffNote,
    MedAdministration,
    Medication,
    Person,
    Shift,
)
from app.services import activity
from app.services.people import load_preferences


@dataclass
class MedRow:
    id: str
    name: str
    dose_text: str
    scheduled_time: str
    display_time: str
    shifted: bool
    shift_reason: str
    instructions: str
    entered_by: str
    given: bool
    given_by: str = ""
    given_at: Optional[datetime] = None


@dataclass
class NoteRow:
    text: str
    author: str
    when: datetime


@dataclass
class AppointmentRow:
    title: str
    when: datetime
    location: str
    escort: str


@dataclass
class WithheldRow:
    label: str
    reason: str


@dataclass
class ShiftCard:
    shift: Shift
    elder: Person
    caregiver: Person
    visible: FrozenSet[DataCategory]
    # --- content, present only when its category passed both filters ---
    prayer_times: List = field(default_factory=list)
    prayer_buffer_min: int = 0
    meds: List[MedRow] = field(default_factory=list)
    diet_lines: List[str] = field(default_factory=list)
    language_lines: List[str] = field(default_factory=list)
    care_prefs: List[str] = field(default_factory=list)
    personal_care: List[NoteRow] = field(default_factory=list)
    mood_notes: List[NoteRow] = field(default_factory=list)
    appointments: List[AppointmentRow] = field(default_factory=list)
    handoff_in: Optional[NoteRow] = None
    handoff_out: Optional[NoteRow] = None
    withheld: List[WithheldRow] = field(default_factory=list)
    gender_warning: str = ""
    has_dignity_content: bool = False

    def shows(self, category: DataCategory) -> bool:
        return category in self.visible

    def to_dict(self) -> dict:
        """The wire format.

        Absence is the mechanism. A section blocked by Filter A is not present
        as an empty list or a `false` flag -- the key is simply not there, so
        there is nothing in the response for devtools to find and nothing for
        the client to accidentally render.
        """
        payload = {
            "shift": {
                "id": self.shift.id,
                "date": self.shift.date.isoformat(),
                "weekday": self.shift.date.strftime("%A"),
                "date_label": self.shift.date.strftime("%A, %B %-d"),
                "start": self.shift.start,
                "end": self.shift.end,
                "label": self.shift.label,
                "includes_personal_care": bool(self.shift.includes_personal_care),
            },
            "elder": {"name": self.elder.name, "first_name": self.elder.name.split(" ")[0]},
            "caregiver": {"name": self.caregiver.name, "first_name": self.caregiver.name.split(" ")[0]},
            "visible": sorted(c.value for c in self.visible),
            "withheld": [{"label": w.label, "reason": w.reason} for w in self.withheld],
            "gender_warning": self.gender_warning,
            "has_dignity_content": self.has_dignity_content,
        }
        if DataCategory.PREFERENCES in self.visible:
            payload["prayer"] = {
                "times": [{"name": n, "at": t} for n, t in self.prayer_times],
                "buffer_min": self.prayer_buffer_min,
            }
            payload["diet"] = self.diet_lines
            payload["language"] = self.language_lines
            payload["care_preferences"] = self.care_prefs
        if DataCategory.MEDS_SCHEDULE in self.visible:
            payload["medications"] = [
                {
                    "id": m.id,
                    "name": m.name,
                    "dose_text": m.dose_text,
                    "scheduled_time": m.scheduled_time,
                    "display_time": m.display_time,
                    "shifted": m.shifted,
                    "shift_reason": m.shift_reason,
                    "instructions": m.instructions,
                    "entered_by": m.entered_by,
                    "given": m.given,
                    "given_by": m.given_by,
                    "given_at": m.given_at.isoformat(timespec="minutes") if m.given_at else None,
                }
                for m in self.meds
            ]
        if DataCategory.APPOINTMENTS in self.visible and self.appointments:
            payload["appointments"] = [
                {
                    "title": a.title,
                    "at": a.when.isoformat(timespec="minutes"),
                    "time": a.when.strftime("%H:%M"),
                    "location": a.location,
                    "escort": a.escort,
                }
                for a in self.appointments
            ]
        if DataCategory.PERSONAL_CARE_LOG in self.visible:
            payload["personal_care"] = [_note_dict(n) for n in self.personal_care]
            payload["handoff_in"] = _note_dict(self.handoff_in) if self.handoff_in else None
            payload["handoff_out"] = _note_dict(self.handoff_out) if self.handoff_out else None
        if DataCategory.MOOD_NOTES in self.visible:
            payload["mood_notes"] = [_note_dict(n) for n in self.mood_notes]
        return payload


def _note_dict(note: "NoteRow") -> dict:
    return {
        "text": note.text,
        "author": note.author,
        "when": note.when.isoformat(timespec="minutes"),
        "day": note.when.strftime("%-d %b"),
    }


def relevance_context(db: Session, shift: Shift) -> RelevanceContext:
    """Filter B's inputs, computed once per card."""
    return RelevanceContext(
        surface=Surface.SHIFT_CARD,
        shift_includes_personal_care=bool(shift.includes_personal_care),
        has_appointment_in_window=_appointment_in_window(db, shift) is not None,
    )


def build_shift_card(
    db: Session,
    *,
    shift: Shift,
    viewer: Person,
    elder: Person,
    log_disclosure: bool = True,
) -> ShiftCard:
    ctx = relevance_context(db, shift)
    visible = visible_categories(viewer, ctx)
    prefs = load_preferences(db, elder.id)

    card = ShiftCard(
        shift=shift,
        elder=elder,
        caregiver=viewer,
        visible=visible,
        prayer_buffer_min=prefs.prayer_times.buffer_min,
    )

    if DataCategory.PREFERENCES in visible:
        card.prayer_times = prefs.prayer_times.all_times()
        card.diet_lines = _diet_lines(prefs)
        card.language_lines = _language_lines(prefs)
        card.care_prefs = _care_pref_lines(prefs)

    if DataCategory.MEDS_SCHEDULE in visible:
        card.meds = _med_rows(db, elder=elder, shift=shift, prefs=prefs)

    if DataCategory.APPOINTMENTS in visible:
        appt = _appointment_in_window(db, shift)
        if appt is not None:
            card.appointments = [
                AppointmentRow(appt.title, appt.starts_at, appt.location, appt.escort)
            ]

    if DataCategory.PERSONAL_CARE_LOG in visible:
        card.personal_care = _notes(db, elder.id, DataCategory.PERSONAL_CARE_LOG, limit=3)
        card.handoff_in = _last_handoff(db, elder.id, before_shift=shift)
        card.handoff_out = _handoff_for_shift(db, shift)

    if DataCategory.MOOD_NOTES in visible:
        card.mood_notes = _notes(db, elder.id, DataCategory.MOOD_NOTES, limit=3)

    card.has_dignity_content = bool(visible & DIGNITY_SENSITIVE)

    # Categories this person may see, but not on this shift. Naming these is
    # safe -- they passed Filter A. Categories blocked by Filter A are never
    # named, and never reach this object at all.
    card.withheld = [
        WithheldRow(CATEGORY_LABELS[c], _relevance_reason(c, ctx))
        for c in sorted(withheld_as_irrelevant(viewer, ctx), key=lambda c: c.value)
    ]

    check = check_bathing_assignment(prefs, viewer.gender, bool(shift.includes_personal_care))
    card.gender_warning = check.warning

    if log_disclosure:
        activity.record_disclosure(
            db,
            elder_id=elder.id,
            viewer=viewer,
            surface_label="Shift card, {} {}-{}".format(shift.date.isoformat(), shift.start, shift.end),
            categories=visible,
        )
    return card


def mark_med_given(
    db: Session, *, shift: Shift, medication_id: str, viewer: Person, elder: Person
) -> Optional[Medication]:
    """Records that a person gave a dose. The app makes no clinical judgement:
    it stores who pressed the button and when."""
    ctx = relevance_context(db, shift)
    if DataCategory.MEDS_SCHEDULE not in visible_categories(viewer, ctx):
        return None  # re-checked at write time, not just at render time

    med = db.get(Medication, medication_id)
    if med is None or med.elder_id != elder.id:
        return None
    already = db.execute(
        select(MedAdministration).where(
            MedAdministration.medication_id == med.id,
            MedAdministration.shift_id == shift.id,
        )
    ).scalars().first()
    if already is not None:
        return med

    db.add(
        MedAdministration(
            medication_id=med.id, shift_id=shift.id, given_by_id=viewer.id, given_at=datetime.utcnow()
        )
    )
    db.flush()
    activity.record(
        db,
        elder_id=elder.id,
        actor=viewer,
        kind=LogEntryKind.CARE,
        action="{} marked {} as given".format(viewer.name, med.name),
        detail="Scheduled {}".format(med.scheduled_time),
        icon="M",
        categories=[DataCategory.MEDS_SCHEDULE],
        commit=False,
    )
    db.commit()
    return med


def write_handoff(
    db: Session, *, shift: Shift, viewer: Person, elder: Person, text: str
) -> Optional[HandoffNote]:
    """One line for the next caregiver."""
    text = (text or "").strip()
    if not text:
        return None
    ctx = relevance_context(db, shift)
    if DataCategory.PERSONAL_CARE_LOG not in visible_categories(viewer, ctx):
        return None

    note = _handoff_for_shift(db, shift, raw=True)
    if note is not None:
        note.text = text
        note.created_at = datetime.utcnow()
    else:
        note = HandoffNote(shift_id=shift.id, elder_id=elder.id, author_id=viewer.id, text=text)
        db.add(note)
    db.flush()
    activity.record(
        db,
        elder_id=elder.id,
        actor=viewer,
        kind=LogEntryKind.CARE,
        action="{} left a handoff note for the next caregiver".format(viewer.name),
        detail=text,
        icon="H",
        categories=[DataCategory.PERSONAL_CARE_LOG],
        commit=False,
    )
    db.commit()
    return note


# --------------------------------------------------------------------------
# internals
# --------------------------------------------------------------------------

def _med_rows(db: Session, *, elder: Person, shift: Shift, prefs: Preferences) -> List[MedRow]:
    meds = db.execute(
        select(Medication).where(Medication.elder_id == elder.id).order_by(Medication.scheduled_time)
    ).scalars().all()
    given = {
        a.medication_id: a
        for a in db.execute(
            select(MedAdministration).where(MedAdministration.shift_id == shift.id)
        ).scalars().all()
    }
    names = {p.id: p.name for p in db.execute(select(Person)).scalars().all()}

    rows: List[MedRow] = []
    for med in meds:
        ts = apply_prayer_buffer(med.scheduled_time, prefs)
        if not _within_shift(ts.display_time, shift):
            continue
        record = given.get(med.id)
        rows.append(
            MedRow(
                id=med.id,
                name=med.name,
                dose_text=med.dose_text,
                scheduled_time=med.scheduled_time,
                display_time=ts.display_time,
                shifted=ts.shifted,
                shift_reason=ts.reason,
                instructions=med.instructions,
                entered_by=med.entered_by,
                given=record is not None,
                given_by=names.get(record.given_by_id, "") if record else "",
                given_at=record.given_at if record else None,
            )
        )
    rows.sort(key=lambda r: r.display_time)
    return rows


#: A dose due shortly before a shift begins still belongs on that shift's
#: card -- especially once a prayer buffer has pushed it forward into the
#: shift. Doses due after the shift ends belong to whoever comes next.
SHIFT_LEAD_IN_MIN = 45


def _within_shift(hhmm_value: str, shift: Shift) -> bool:
    at = minutes(hhmm_value)
    return minutes(shift.start) - SHIFT_LEAD_IN_MIN <= at <= minutes(shift.end)


def _appointment_in_window(db: Session, shift: Shift) -> Optional[Appointment]:
    """Filter B for appointments: only one that lands on this shift, not the
    elder's whole calendar."""
    start = datetime.combine(shift.date, datetime.min.time()) + timedelta(minutes=minutes(shift.start) - 60)
    end = datetime.combine(shift.date, datetime.min.time()) + timedelta(minutes=minutes(shift.end))
    return db.execute(
        select(Appointment)
        .where(Appointment.starts_at >= start, Appointment.starts_at <= end)
        .order_by(Appointment.starts_at)
    ).scalars().first()


def _notes(db: Session, elder_id: str, category: DataCategory, limit: int = 3) -> List[NoteRow]:
    notes = db.execute(
        select(CareNote)
        .where(CareNote.elder_id == elder_id, CareNote.category == category.value)
        .order_by(CareNote.created_at.desc())
        .limit(limit)
    ).scalars().all()
    names = {p.id: p.name for p in db.execute(select(Person)).scalars().all()}
    return [NoteRow(n.text, names.get(n.author_id or "", "Unattributed"), n.created_at) for n in notes]


def _last_handoff(db: Session, elder_id: str, *, before_shift: Shift) -> Optional[NoteRow]:
    note = db.execute(
        select(HandoffNote)
        .where(HandoffNote.elder_id == elder_id, HandoffNote.shift_id != before_shift.id)
        .order_by(HandoffNote.created_at.desc())
    ).scalars().first()
    if note is None:
        return None
    author = db.get(Person, note.author_id)
    return NoteRow(note.text, author.name if author else "A caregiver", note.created_at)


def _handoff_for_shift(db: Session, shift: Shift, raw: bool = False):
    note = db.execute(
        select(HandoffNote).where(HandoffNote.shift_id == shift.id).order_by(HandoffNote.created_at.desc())
    ).scalars().first()
    if note is None or raw:
        return note
    author = db.get(Person, note.author_id)
    return NoteRow(note.text, author.name if author else "A caregiver", note.created_at)


def _diet_lines(prefs: Preferences) -> List[str]:
    lines = ["Meat: {}".format(MEAT_LABELS[prefs.diet.meat])]
    if prefs.diet.meat == "other" and prefs.diet.meat_other:
        lines.append("Note on meat: {}".format(prefs.diet.meat_other))
    lines.append(
        "Seafood: {}".format("no restriction" if prefs.diet.seafood == "any" else "restricted")
    )
    if prefs.diet.substitutes:
        lines.append("Substitutes on hand: {}".format(", ".join(prefs.diet.substitutes)))
    return lines


def _language_lines(prefs: Preferences) -> List[str]:
    lines = []
    if prefs.language.spoken:
        lines.append("Speaks: {}".format(prefs.language.spoken))
    if prefs.language.written:
        lines.append("Reads: {}".format(prefs.language.written))
    return lines


def _care_pref_lines(prefs: Preferences) -> List[str]:
    cg = prefs.caregiver_gender
    return [
        "Bathing: {}".format(GENDER_LABELS[cg.bathing]),
        "Meals: {}".format(GENDER_LABELS[cg.meals]),
        "Transport: {}".format(GENDER_LABELS[cg.transport]),
    ]


def _relevance_reason(category: DataCategory, ctx: RelevanceContext) -> str:
    if category is DataCategory.APPOINTMENTS:
        return "Nothing scheduled during this shift."
    if category is DataCategory.PERSONAL_CARE_LOG:
        return "This shift has no personal care on it."
    if category is DataCategory.MOOD_NOTES:
        return "This shift has no personal care on it."
    if category is DataCategory.FINANCES:
        return "Money is never shown on a shift card."
    return "Not part of this shift."
