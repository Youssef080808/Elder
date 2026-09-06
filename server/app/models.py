"""SQLAlchemy tables.

Every table holding information about the elder carries the data category it
belongs to -- either by being category-specific (Medication -> meds_schedule)
or by storing the category on the row (CareNote). Nothing about her is
renderable until it has a category, because the permission engine keys off
categories and nothing else.
"""
from __future__ import annotations

import uuid
from datetime import date as Date
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Date as SADate,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.domain.logbook import LogEntryKind  # noqa: F401  (re-exported for services)


def _uid() -> str:
    return uuid.uuid4().hex[:12]


class Role(str):
    ELDER = "elder"
    FAMILY = "family"
    CAREGIVER = "caregiver"


class Person(Base):
    __tablename__ = "people"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)  # elder | family | caregiver
    #: What the UI prints under the name, e.g. "Son - family".
    role_label: Mapped[str] = mapped_column(String, default="")
    initials: Mapped[str] = mapped_column(String, default="")
    tone: Mapped[str] = mapped_column(String, default="")
    #: Needed because caregiver_gender preferences filter shift assignment.
    gender: Mapped[str] = mapped_column(String, default="unspecified")

    elder_id: Mapped[Optional[str]] = mapped_column(ForeignKey("people.id"), nullable=True)

    #: At most one Person per elder may be true (enforced in domain/proxy.py).
    is_proxy: Mapped[bool] = mapped_column(Boolean, default=False)
    #: Delegation is time-bounded by default.
    proxy_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    permissions: Mapped[List["Permission"]] = relationship(
        back_populates="person",
        cascade="all, delete-orphan",
        lazy="selectin",
        foreign_keys="Permission.person_id",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "<Person {} ({})>".format(self.name, self.role)


class Permission(Base):
    """One row per (person, category). Permissions belong to the person, not
    the role: editing one person's column cannot touch another's."""

    __tablename__ = "permissions"
    __table_args__ = (UniqueConstraint("person_id", "category", name="uq_person_category"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uid)
    person_id: Mapped[str] = mapped_column(ForeignKey("people.id"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String, nullable=False)
    granted: Mapped[bool] = mapped_column(Boolean, default=False)

    person: Mapped[Person] = relationship(back_populates="permissions", foreign_keys=[person_id])


class PreferenceRecord(Base):
    """The elder's structured Preferences object (app/domain/preferences.py)."""

    __tablename__ = "preference_records"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uid)
    elder_id: Mapped[str] = mapped_column(ForeignKey("people.id"), nullable=False, unique=True)
    data: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)


class Medication(Base):
    """Category: meds_schedule.

    Every field here is transcribed from what a human entered. This app does
    not advise on medication: no dose suggestions, no interaction checks, no
    triage. It shows a schedule and records that a person acted on it.
    """

    __tablename__ = "medications"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uid)
    elder_id: Mapped[str] = mapped_column(ForeignKey("people.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    dose_text: Mapped[str] = mapped_column(String, default="")
    scheduled_time: Mapped[str] = mapped_column(String, nullable=False)  # "HH:MM"
    instructions: Mapped[str] = mapped_column(Text, default="")
    entered_by: Mapped[str] = mapped_column(String, default="")  # provenance, shown in the UI


class MedAdministration(Base):
    """A caregiver recording that a scheduled dose was given: an action by a
    person, not a clinical judgement by the app."""

    __tablename__ = "med_administrations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uid)
    medication_id: Mapped[str] = mapped_column(ForeignKey("medications.id"), nullable=False, index=True)
    shift_id: Mapped[str] = mapped_column(ForeignKey("shifts.id"), nullable=False, index=True)
    given_by_id: Mapped[str] = mapped_column(ForeignKey("people.id"), nullable=False)
    given_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Appointment(Base):
    """Category: appointments."""

    __tablename__ = "appointments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uid)
    elder_id: Mapped[str] = mapped_column(ForeignKey("people.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    location: Mapped[str] = mapped_column(String, default="")
    escort: Mapped[str] = mapped_column(String, default="")


class CareNote(Base):
    """Categories: personal_care_log and mood_notes.

    Both are timestamped text a person wrote about the elder, so they share a
    table -- but they are separate categories in the grid, which is the point:
    Amira can let a paid caregiver log bathing assistance without handing over
    how she seemed on Tuesday afternoon.
    """

    __tablename__ = "care_notes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uid)
    elder_id: Mapped[str] = mapped_column(ForeignKey("people.id"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[Optional[str]] = mapped_column(ForeignKey("people.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FinanceItem(Base):
    """Category: finances. Never granted by a preset."""

    __tablename__ = "finance_items"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uid)
    elder_id: Mapped[str] = mapped_column(ForeignKey("people.id"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String, nullable=False)
    detail: Mapped[str] = mapped_column(String, default="")


class Shift(Base):
    __tablename__ = "shifts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uid)
    elder_id: Mapped[str] = mapped_column(ForeignKey("people.id"), nullable=False, index=True)
    caregiver_id: Mapped[Optional[str]] = mapped_column(ForeignKey("people.id"), nullable=True)
    date: Mapped[Date] = mapped_column(SADate, nullable=False, index=True)
    start: Mapped[str] = mapped_column(String, nullable=False)  # "HH:MM"
    end: Mapped[str] = mapped_column(String, nullable=False)    # "HH:MM"
    covered: Mapped[bool] = mapped_column(Boolean, default=False)
    #: Drives both the caregiver_gender.bathing consequence and relevance.
    includes_personal_care: Mapped[bool] = mapped_column(Boolean, default=False)
    label: Mapped[str] = mapped_column(String, default="")


class HandoffNote(Base):
    """One line left by the outgoing caregiver for the incoming one."""

    __tablename__ = "handoff_notes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uid)
    shift_id: Mapped[str] = mapped_column(ForeignKey("shifts.id"), nullable=False, index=True)
    elder_id: Mapped[str] = mapped_column(ForeignKey("people.id"), nullable=False, index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("people.id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class LogEntry(Base):
    __tablename__ = "log_entries"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uid)
    elder_id: Mapped[str] = mapped_column(ForeignKey("people.id"), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey("people.id"), nullable=False)
    acting_as_proxy: Mapped[bool] = mapped_column(Boolean, default=False)
    kind: Mapped[str] = mapped_column(String, default=LogEntryKind.CARE)
    action: Mapped[str] = mapped_column(Text, nullable=False)  # human-readable
    detail: Mapped[str] = mapped_column(Text, default="")
    icon: Mapped[str] = mapped_column(String, default="V")
    target_person_id: Mapped[Optional[str]] = mapped_column(ForeignKey("people.id"), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    #: Set on disclosure rows so the elder can see exactly which categories
    #: were on screen, and so repeat views collapse instead of spamming.
    categories: Mapped[Optional[str]] = mapped_column(String, default="")
    sort_seq: Mapped[int] = mapped_column(Integer, default=0)
