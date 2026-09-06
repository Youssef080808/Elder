"""The elder's preferences, and the two places they change what a caregiver sees.

Rule used throughout: if code branches on the value it is an enum; if only a
human reads it, it is text. Enums that need flexibility carry a fixed option
list plus an `_other` companion that displays but drives no logic.

"Muslim-friendly" is never one setting. There is no such flag anywhere in this
file. Every cultural preference is an individual field with its own value,
because a Somali grandmother in Minneapolis and a Bangladeshi grandfather in
Luton do not share a checkbox.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

GENDER_OPTIONS: Tuple[str, ...] = ("female", "male", "any")
MEAT_OPTIONS: Tuple[str, ...] = ("zabiha_only", "halal_certified", "any", "other")
SEAFOOD_OPTIONS: Tuple[str, ...] = ("any", "restricted")
PRAYER_METHODS: Tuple[str, ...] = ("ISNA", "MWL", "Umm al-Qura", "Egyptian", "Karachi")

MEAT_LABELS: Dict[str, str] = {
    "zabiha_only": "Zabiha only",
    "halal_certified": "Halal certified",
    "any": "No restriction",
    "other": "Other (see note)",
}
GENDER_LABELS: Dict[str, str] = {
    "female": "Female caregiver",
    "male": "Male caregiver",
    "any": "No preference",
}


@dataclass
class CaregiverGender:
    """Per task, not per person. Someone may want a woman for bathing and not
    care who drives them to the clinic."""

    bathing: str = "any"
    meals: str = "any"
    transport: str = "any"


@dataclass
class PrayerTimes:
    method: str = "ISNA"
    #: Minutes to leave clear after a prayer before medication is offered.
    #: This is the one number that moves a time on the caregiver's screen.
    buffer_min: int = 0
    fajr: str = "05:40"
    dhuhr: str = "13:10"
    asr: str = "16:45"
    maghrib: str = "19:55"
    isha: str = "21:20"

    def all_times(self) -> List[Tuple[str, str]]:
        return [
            ("Fajr", self.fajr),
            ("Dhuhr", self.dhuhr),
            ("Asr", self.asr),
            ("Maghrib", self.maghrib),
            ("Isha", self.isha),
        ]


@dataclass
class Diet:
    meat: str = "any"
    meat_other: str = ""          # displays only, drives no logic
    seafood: str = "any"
    substitutes: List[str] = field(default_factory=list)


@dataclass
class Language:
    spoken: str = ""
    written: str = ""


@dataclass
class Preferences:
    caregiver_gender: CaregiverGender = field(default_factory=CaregiverGender)
    prayer_times: PrayerTimes = field(default_factory=PrayerTimes)
    diet: Diet = field(default_factory=Diet)
    language: Language = field(default_factory=Language)
    notes: str = ""               # free text, displays only, drives no logic

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Optional[Dict[str, Any]]) -> "Preferences":
        data = data or {}
        cg = data.get("caregiver_gender", {}) or {}
        pt = data.get("prayer_times", {}) or {}
        di = data.get("diet", {}) or {}
        la = data.get("language", {}) or {}
        return Preferences(
            caregiver_gender=CaregiverGender(
                bathing=_one_of(cg.get("bathing"), GENDER_OPTIONS, "any"),
                meals=_one_of(cg.get("meals"), GENDER_OPTIONS, "any"),
                transport=_one_of(cg.get("transport"), GENDER_OPTIONS, "any"),
            ),
            prayer_times=PrayerTimes(
                method=_one_of(pt.get("method"), PRAYER_METHODS, "ISNA"),
                buffer_min=_clamp_int(pt.get("buffer_min"), 0, 0, 180),
                fajr=_hhmm(pt.get("fajr"), "05:40"),
                dhuhr=_hhmm(pt.get("dhuhr"), "13:10"),
                asr=_hhmm(pt.get("asr"), "16:45"),
                maghrib=_hhmm(pt.get("maghrib"), "19:55"),
                isha=_hhmm(pt.get("isha"), "21:20"),
            ),
            diet=Diet(
                meat=_one_of(di.get("meat"), MEAT_OPTIONS, "any"),
                meat_other=str(di.get("meat_other") or ""),
                seafood=_one_of(di.get("seafood"), SEAFOOD_OPTIONS, "any"),
                substitutes=[s for s in (di.get("substitutes") or []) if str(s).strip()],
            ),
            language=Language(
                spoken=str(la.get("spoken") or ""),
                written=str(la.get("written") or ""),
            ),
            notes=str(data.get("notes") or ""),
        )


# --------------------------------------------------------------------------
# Consequence 1: prayer buffer shifts the medication time on the shift card.
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class TimeShift:
    display_time: str
    shifted: bool
    shifted_by_min: int
    reason: str


def minutes(hhmm: str) -> int:
    h, _, m = hhmm.partition(":")
    return int(h) * 60 + int(m)


def hhmm(total_minutes: int) -> str:
    total_minutes %= 24 * 60
    return "{:02d}:{:02d}".format(total_minutes // 60, total_minutes % 60)


def apply_prayer_buffer(scheduled: str, prefs: Preferences) -> TimeShift:
    """Push a scheduled dose out of a prayer's buffer window.

    This is a scheduling courtesy applied to a time a human already entered.
    It never changes what the medication is, how much of it, or whether to
    give it -- only when it is offered, so a dose is not pressed on someone
    mid-prayer.
    """
    buffer_min = prefs.prayer_times.buffer_min
    if buffer_min <= 0:
        return TimeShift(scheduled, False, 0, "")

    at = minutes(scheduled)
    for name, prayer in prefs.prayer_times.all_times():
        start = minutes(prayer)
        end = start + buffer_min
        if start <= at < end:
            return TimeShift(
                display_time=hhmm(end),
                shifted=True,
                shifted_by_min=end - at,
                reason="moved from {} to clear the {}-minute buffer after {} ({})".format(
                    scheduled, buffer_min, name, prayer
                ),
            )
    return TimeShift(scheduled, False, 0, "")


# --------------------------------------------------------------------------
# Consequence 2: caregiver gender filters / warns on shift assignment.
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class GenderCheck:
    ok: bool
    warning: str = ""


def check_bathing_assignment(
    prefs: Preferences,
    caregiver_gender: Optional[str],
    shift_includes_personal_care: bool,
) -> GenderCheck:
    """A shift with bathing on it, staffed against the elder's stated wish, is
    surfaced as a warning on the coverage list rather than silently allowed."""
    if not shift_includes_personal_care:
        return GenderCheck(True)
    wanted = prefs.caregiver_gender.bathing
    if wanted == "any":
        return GenderCheck(True)
    if not caregiver_gender or caregiver_gender == "unspecified":
        return GenderCheck(
            False,
            "This shift includes bathing. {} is preferred and this caregiver's "
            "gender is not recorded.".format(GENDER_LABELS[wanted]),
        )
    if caregiver_gender != wanted:
        return GenderCheck(
            False,
            "This shift includes bathing and {} is preferred.".format(
                GENDER_LABELS[wanted].lower()
            ),
        )
    return GenderCheck(True)


# --------------------------------------------------------------------------

def _one_of(value: Any, options: Tuple[str, ...], default: str) -> str:
    value = str(value or "").strip()
    return value if value in options else default


def _clamp_int(value: Any, default: int, low: int, high: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, n))


def _hhmm(value: Any, default: str) -> str:
    value = str(value or "").strip()
    if len(value) == 5 and value[2] == ":" and value[:2].isdigit() and value[3:].isdigit():
        if 0 <= int(value[:2]) < 24 and 0 <= int(value[3:]) < 60:
            return value
    return default
