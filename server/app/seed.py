"""Deterministic demo data, matching the cast the front end already knows:
Amira Hassan, cared for by Fatima Rahman (paid), Omar (son) and Sara
(daughter).

Reseeding on boot is the deliberate hackathon tradeoff: no volume to mount, no
migrations, and every demo starts from the same known state.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import Base, SessionLocal, engine
from app.domain.categories import DataCategory, Preset, preset_grants
from app.domain.logbook import LogEntryKind
from app.domain.preferences import Preferences
from app.models import (
    Appointment,
    CareNote,
    FinanceItem,
    HandoffNote,
    Medication,
    Permission,
    Person,
    PreferenceRecord,
    Shift,
)
from app.services import activity
from app.services.consent import ensure_permission_rows

ELDER_ID = "amira"
FATIMA_ID = "fatima"
OMAR_ID = "omar"
SARA_ID = "sara"


def reset_database() -> None:
    """Drop and rebuild. `dispose` first so a connection left open by an
    earlier failure cannot turn this into a SQLite lock wait."""
    engine.dispose()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def seed(db: Session, today: date = None) -> Person:
    today = today or date.today()

    elder = Person(
        id=ELDER_ID,
        name="Amira Hassan",
        role="elder",
        role_label="82, lives at home",
        initials="AH",
        gender="female",
    )
    db.add(elder)
    db.flush()
    elder.elder_id = elder.id

    fatima = Person(
        id=FATIMA_ID, name="Fatima Rahman", role="caregiver", role_label="Paid caregiver",
        initials="FR", tone="gold", gender="female", elder_id=elder.id,
    )
    omar = Person(
        id=OMAR_ID, name="Omar Hassan", role="family", role_label="Son · family",
        initials="OH", gender="male", elder_id=elder.id,
    )
    sara = Person(
        id=SARA_ID, name="Sara Hassan", role="family", role_label="Daughter · family",
        initials="SH", gender="female", elder_id=elder.id,
    )
    db.add_all([fatima, omar, sara])
    db.flush()

    for person, preset in (
        (fatima, Preset.PAID_CAREGIVER),
        (omar, Preset.CLOSE_FAMILY),
        (sara, Preset.VISITING_RELATIVE),
    ):
        ensure_permission_rows(db, person)
        grants = preset_grants(preset)
        for row in db.execute(
            select(Permission).where(Permission.person_id == person.id)
        ).scalars().all():
            row.granted = DataCategory(row.category) in grants

    db.add(
        PreferenceRecord(
            elder_id=elder.id,
            data=Preferences.from_dict(
                {
                    "caregiver_gender": {"bathing": "female", "meals": "any", "transport": "any"},
                    "prayer_times": {
                        "method": "ISNA", "buffer_min": 20,
                        "fajr": "05:40", "dhuhr": "13:10", "asr": "16:45",
                        "maghrib": "19:55", "isha": "21:20",
                    },
                    "diet": {
                        "meat": "zabiha_only", "meat_other": "", "seafood": "any",
                        "substitutes": ["No dairy substitutes"],
                    },
                    "language": {"spoken": "English and Urdu", "written": "English"},
                    "notes": (
                        "Quiet start to the morning. Knock gently and explain what "
                        "comes next. She will say she is fine when she is not."
                    ),
                }
            ).to_dict(),
        )
    )

    # Medication: every value below was typed in by a person. This app shows a
    # schedule; it does not advise on one.
    entered_by = "Entered by Omar from the clinic letter, 2 March"
    db.add_all(
        [
            Medication(
                elder_id=elder.id, name="Metformin", dose_text="500 mg, one tablet",
                scheduled_time="05:45", instructions="With food, usually with breakfast.",
                entered_by=entered_by,
            ),
            Medication(
                elder_id=elder.id, name="Amlodipine", dose_text="5 mg, one tablet",
                scheduled_time="08:00", instructions="After breakfast.", entered_by=entered_by,
            ),
            Medication(
                elder_id=elder.id, name="Atorvastatin", dose_text="20 mg, one tablet",
                scheduled_time="21:00", instructions="At night.", entered_by=entered_by,
            ),
        ]
    )

    db.add_all(
        [
            Appointment(
                elder_id=elder.id, title="Cardiology follow-up",
                starts_at=datetime.combine(today, time(14, 30)),
                location="Outpatients, second floor", escort="Omar driving",
            ),
            Appointment(
                elder_id=elder.id, title="Podiatry",
                starts_at=datetime.combine(today + timedelta(days=2), time(9, 15)),
                location="Community clinic", escort="Taxi booked",
            ),
        ]
    )

    db.add_all(
        [
            CareNote(
                elder_id=elder.id, category=DataCategory.PERSONAL_CARE_LOG.value,
                text="Prefers to wash before Fajr. Needs a hand with the shower step, not with dressing.",
                author_id=omar.id,
                created_at=datetime.combine(today - timedelta(days=1), time(20, 10)),
            ),
            CareNote(
                elder_id=elder.id, category=DataCategory.MOOD_NOTES.value,
                text="Quiet after the call with her brother. Sat by the window a long time.",
                author_id=sara.id,
                created_at=datetime.combine(today - timedelta(days=1), time(21, 0)),
            ),
        ]
    )

    db.add_all(
        [
            FinanceItem(elder_id=elder.id, label="Care agency direct debit", detail="820 on the 1st"),
            FinanceItem(elder_id=elder.id, label="State pension", detail="Deposited on the 3rd"),
        ]
    )

    shifts = _seed_shifts(db, elder=elder, fatima=fatima, omar=omar, sara=sara, today=today)

    db.add(
        HandoffNote(
            shift_id=shifts["yesterday_evening"].id, elder_id=elder.id, author_id=omar.id,
            text="She slept well. Please start with tea and give her a little extra time this morning.",
            created_at=datetime.combine(today - timedelta(days=1), time(20, 40)),
        )
    )
    db.flush()

    activity.record(
        db, elder_id=elder.id, actor=elder, kind=LogEntryKind.CONSENT, icon="P",
        action="Amira set up her circle and chose what each person can see",
        detail="Three people, three different columns.", commit=False,
    )
    db.commit()
    return elder


def _seed_shifts(db: Session, *, elder, fatima, omar, sara, today: date):
    """A week with real gaps in it, and one shift staffed against Amira's
    stated bathing preference."""

    def make(day_offset, start, end, caregiver, personal_care, label):
        shift = Shift(
            elder_id=elder.id,
            caregiver_id=caregiver.id if caregiver else None,
            date=today + timedelta(days=day_offset),
            start=start, end=end,
            covered=caregiver is not None,
            includes_personal_care=personal_care,
            label=label,
        )
        db.add(shift)
        return shift

    made = {
        # Yesterday, only so last night's handoff note has somewhere to live.
        "yesterday_evening": make(-1, "17:00", "20:00", omar, False, "Evening"),
        # Today is Fatima's 6am shift -- the one the demo opens.
        "today_morning": make(0, "06:00", "14:00", fatima, True, "Morning, personal care"),
        "today_evening": make(0, "17:00", "20:00", sara, False, "Evening"),
        "d1_morning": make(1, "06:00", "14:00", fatima, True, "Morning, personal care"),
        # Omar on an evening that includes bathing: the row that lights up,
        # because Amira asked for a woman for bathing.
        "d1_evening": make(1, "17:00", "20:00", omar, True, "Evening, personal care"),
        "d2_morning": make(2, "06:00", "14:00", fatima, False, "Morning"),
        # Day 3 has nothing at all. That is the point of the coverage screen.
        "d4_morning": make(4, "06:00", "14:00", fatima, True, "Morning, personal care"),
        # Day 5's morning exists but nobody is on it.
        "d5_morning": make(5, "06:00", "14:00", None, True, "Morning, personal care"),
        "d5_evening": make(5, "17:00", "20:00", sara, False, "Evening"),
        # Day 6 is the second empty day.
    }
    db.flush()
    return made


def reseed() -> None:
    reset_database()
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


if __name__ == "__main__":  # pragma: no cover
    reseed()
    print("Seeded.")
