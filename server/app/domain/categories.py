"""The fixed list of data categories, and the three presets that stamp them.

These are the rows of the elder's permission grid. The list is deliberately
closed: a new kind of information about an elder must be classified into a
category before it can ever be rendered, which is what makes the grid a
complete answer to "who can see what about me right now".
"""
from __future__ import annotations

from enum import Enum
from typing import Dict, FrozenSet, List, Tuple


class DataCategory(str, Enum):
    """Every piece of elder information belongs to exactly one of these."""

    MEDS_SCHEDULE = "meds_schedule"          # names + times a human entered
    APPOINTMENTS = "appointments"
    PREFERENCES = "preferences"              # prayer, diet, language, caregiver gender
    PERSONAL_CARE_LOG = "personal_care_log"  # bathing, dressing, toileting
    MOOD_NOTES = "mood_notes"
    FINANCES = "finances"


#: Grid row order. Logistics first, dignity-sensitive next, money last.
CATEGORY_ORDER: Tuple[DataCategory, ...] = (
    DataCategory.MEDS_SCHEDULE,
    DataCategory.APPOINTMENTS,
    DataCategory.PREFERENCES,
    DataCategory.PERSONAL_CARE_LOG,
    DataCategory.MOOD_NOTES,
    DataCategory.FINANCES,
)

#: Categories where a disclosure is a dignity cost, not just a logistics cost.
#: These views are render-only: no export, no download, no copy-to-clipboard.
DIGNITY_SENSITIVE: FrozenSet[DataCategory] = frozenset(
    {DataCategory.PERSONAL_CARE_LOG, DataCategory.MOOD_NOTES, DataCategory.FINANCES}
)

CATEGORY_LABELS: Dict[DataCategory, str] = {
    DataCategory.MEDS_SCHEDULE: "Medication schedule",
    DataCategory.APPOINTMENTS: "Appointments",
    DataCategory.PREFERENCES: "Preferences",
    DataCategory.PERSONAL_CARE_LOG: "Personal care log",
    DataCategory.MOOD_NOTES: "Mood notes",
    DataCategory.FINANCES: "Finances",
}

#: The short label and single-letter icon the front end renders per row.
CATEGORY_SHORT: Dict[DataCategory, str] = {
    DataCategory.MEDS_SCHEDULE: "Names + times",
    DataCategory.APPOINTMENTS: "Upcoming visits",
    DataCategory.PREFERENCES: "Daily choices",
    DataCategory.PERSONAL_CARE_LOG: "Dignity-sensitive",
    DataCategory.MOOD_NOTES: "Private observations",
    DataCategory.FINANCES: "Private records",
}

CATEGORY_ICONS: Dict[DataCategory, str] = {
    DataCategory.MEDS_SCHEDULE: "M",
    DataCategory.APPOINTMENTS: "A",
    DataCategory.PREFERENCES: "P",
    DataCategory.PERSONAL_CARE_LOG: "C",
    DataCategory.MOOD_NOTES: "N",
    DataCategory.FINANCES: "$",
}

CATEGORY_BLURBS: Dict[DataCategory, str] = {
    DataCategory.MEDS_SCHEDULE: "What to give and when. Entered by a person, never advised by this app.",
    DataCategory.APPOINTMENTS: "Where I need to be, and who is taking me.",
    DataCategory.PREFERENCES: "Prayer, diet, language, who may help me with what.",
    DataCategory.PERSONAL_CARE_LOG: "Bathing, dressing, toileting assistance.",
    DataCategory.MOOD_NOTES: "How I seemed today. The most personal thing here.",
    DataCategory.FINANCES: "Money. Granted one toggle at a time, never by a preset.",
}


class Preset(str, Enum):
    """Exactly three. A preset stamps values into one person's column; after
    stamping, the values belong to that person and diverge freely."""

    CLOSE_FAMILY = "close_family"
    PAID_CAREGIVER = "paid_caregiver"
    VISITING_RELATIVE = "visiting_relative"


PRESET_GRANTS: Dict[Preset, FrozenSet[DataCategory]] = {
    Preset.CLOSE_FAMILY: frozenset(DataCategory),
    Preset.PAID_CAREGIVER: frozenset(
        {
            DataCategory.MEDS_SCHEDULE,
            DataCategory.APPOINTMENTS,
            DataCategory.PREFERENCES,
            DataCategory.PERSONAL_CARE_LOG,
        }
    ),
    Preset.VISITING_RELATIVE: frozenset(
        {DataCategory.APPOINTMENTS, DataCategory.PREFERENCES}
    ),
}

PRESET_LABELS: Dict[Preset, str] = {
    Preset.CLOSE_FAMILY: "Close family",
    Preset.PAID_CAREGIVER: "Paid caregiver",
    Preset.VISITING_RELATIVE: "Visiting relative",
}

PRESET_BLURBS: Dict[Preset, str] = {
    Preset.CLOSE_FAMILY: "All six categories.",
    Preset.PAID_CAREGIVER: "Meds, appointments, preferences, personal care.",
    Preset.VISITING_RELATIVE: "Appointments and preferences.",
}


def preset_grants(preset: Preset) -> FrozenSet[DataCategory]:
    return PRESET_GRANTS[preset]


def ordered_categories() -> List[DataCategory]:
    return list(CATEGORY_ORDER)
