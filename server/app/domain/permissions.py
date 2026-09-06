"""The permission engine. Every disclosure in this application passes through
`visible_categories`, and nothing else in the codebase decides visibility.

Two independent filters, deliberately not collapsed into one check:

  Filter A - Permission: does this person's column grant this category?
             Set by the elder, or by an active proxy on the elder's behalf.
  Filter B - Relevance:  given this surface and this shift, should the
             category surface right now?

    visible = has_permission(person, category) and is_relevant(...)

They fail differently on purpose. A category blocked by Filter A leaves no
trace at all -- the caregiver cannot tell whether it exists, which is what
"the elder turned mood notes off" has to mean. A category blocked only by
Filter B is scoping, not secrecy: the person is allowed to know it exists,
so the UI may say "not surfaced on this shift".
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Optional

from app.domain.categories import CATEGORY_ORDER, DataCategory


class Surface(str):
    """Where the data is about to be rendered."""

    SHIFT_CARD = "shift_card"        # pushed to a caregiver for one shift
    COVERAGE = "coverage"            # the week's schedule
    FULL_PROFILE = "full_profile"    # the elder's own view of their record


class BlockedBy(str):
    NOTHING = "nothing"
    PERMISSION = "permission"  # Filter A: render nothing, not even an absence
    RELEVANCE = "relevance"    # Filter B: may be shown as "not on this shift"


@dataclass(frozen=True)
class RelevanceContext:
    """Plain facts about the moment, computed by the caller.

    Keeping this a dumb value object is what lets `is_relevant` stay pure and
    exhaustively testable without a database.
    """

    surface: str = Surface.FULL_PROFILE
    shift_includes_personal_care: bool = False
    has_appointment_in_window: bool = False


def has_permission(person, category: DataCategory) -> bool:
    """Filter A. An elder always passes for their own record."""
    if getattr(person, "role", None) == "elder":
        return True
    wanted = category.value if isinstance(category, DataCategory) else str(category)
    for perm in person.permissions:
        if perm.category == wanted:
            return bool(perm.granted)
    return False


def is_relevant(category: DataCategory, ctx: RelevanceContext) -> bool:
    """Filter B.

    A caregiver permitted to see appointments still should not receive the
    full appointment history on a 6am shift card.
    """
    if ctx.surface == Surface.FULL_PROFILE:
        return True

    if ctx.surface == Surface.COVERAGE:
        # The week view is scheduling only. It never carries record content.
        return category is DataCategory.PREFERENCES

    if ctx.surface == Surface.SHIFT_CARD:
        if category is DataCategory.MEDS_SCHEDULE:
            return True
        if category is DataCategory.PREFERENCES:
            return True
        if category is DataCategory.PERSONAL_CARE_LOG:
            return ctx.shift_includes_personal_care
        if category is DataCategory.MOOD_NOTES:
            # Relevant on a hands-on shift; whether it is *shown* is Filter A's
            # call, and for a paid caregiver the answer is usually no.
            return ctx.shift_includes_personal_care
        if category is DataCategory.APPOINTMENTS:
            return ctx.has_appointment_in_window
        if category is DataCategory.FINANCES:
            # Money is never operational to a shift. No permission column can
            # put it on a shift card.
            return False

    return False


def blocked_by(person, category: DataCategory, ctx: RelevanceContext) -> str:
    """Why a category is not visible. Filter A wins: if the elder did not
    grant it, the caller must not learn anything further about it."""
    if not has_permission(person, category):
        return BlockedBy.PERMISSION
    if not is_relevant(category, ctx):
        return BlockedBy.RELEVANCE
    return BlockedBy.NOTHING


def visible_categories(person, ctx: Optional[RelevanceContext] = None) -> FrozenSet[DataCategory]:
    """The single function that decides what anyone may see.

    No route handler and no template calls the ORM for category data; they ask
    a service, and every service asks this. If a caregiver view could fetch a
    category the elder blocked, the entire design would be decoration.
    """
    ctx = ctx or RelevanceContext()
    return frozenset(
        c for c in CATEGORY_ORDER if has_permission(person, c) and is_relevant(c, ctx)
    )


def withheld_as_irrelevant(person, ctx: RelevanceContext) -> FrozenSet[DataCategory]:
    """Categories this person is allowed to see but that this surface is not
    the moment for. Safe to name in the UI; permission-blocked ones are not.
    """
    return frozenset(
        c
        for c in CATEGORY_ORDER
        if has_permission(person, c) and not is_relevant(c, ctx)
    )
