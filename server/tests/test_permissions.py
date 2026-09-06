"""The two filters, tested independently and together.

If `visible_categories` is wrong, every other guarantee in the product is
decoration -- including the one that motivated this backend.
"""
from __future__ import annotations

import pytest

from app.domain.categories import CATEGORY_ORDER, DataCategory as C
from app.domain.permissions import (
    BlockedBy,
    RelevanceContext,
    Surface,
    blocked_by,
    has_permission,
    is_relevant,
    visible_categories,
    withheld_as_irrelevant,
)
from tests.conftest import granted

SHIFT = RelevanceContext(surface=Surface.SHIFT_CARD, shift_includes_personal_care=True)
SHIFT_NO_CARE = RelevanceContext(surface=Surface.SHIFT_CARD, shift_includes_personal_care=False)
SHIFT_WITH_APPT = RelevanceContext(
    surface=Surface.SHIFT_CARD, shift_includes_personal_care=True, has_appointment_in_window=True
)
FULL = RelevanceContext(surface=Surface.FULL_PROFILE)


def test_filter_a_reads_the_persons_own_column(fatima, omar):
    assert has_permission(fatima, C.MEDS_SCHEDULE) is True
    assert has_permission(fatima, C.MOOD_NOTES) is False
    assert has_permission(omar, C.MOOD_NOTES) is True


def test_filter_a_is_per_person_not_per_role(db, fatima, sara, elder):
    """Changing one column must not touch another."""
    from app.services.consent import set_permission

    set_permission(
        db, elder_id=elder.id, actor=elder, target=fatima, category=C.APPOINTMENTS, granted=False
    )
    assert has_permission(fatima, C.APPOINTMENTS) is False
    assert has_permission(sara, C.APPOINTMENTS) is True


def test_elder_always_passes_filter_a_for_her_own_record(elder):
    assert all(has_permission(elder, c) for c in CATEGORY_ORDER)


def test_missing_permission_row_denies(fatima):
    """An absent row and a denied row mean the same thing: no."""
    fatima.permissions = [p for p in fatima.permissions if p.category != C.MEDS_SCHEDULE.value]
    assert has_permission(fatima, C.MEDS_SCHEDULE) is False


def test_filter_b_hides_the_calendar_from_a_6am_shift():
    assert is_relevant(C.APPOINTMENTS, SHIFT) is False
    assert is_relevant(C.APPOINTMENTS, SHIFT_WITH_APPT) is True
    assert is_relevant(C.APPOINTMENTS, FULL) is True


def test_filter_b_never_puts_money_on_a_shift_card():
    """No permission column can override this. Money is not operational."""
    assert is_relevant(C.FINANCES, SHIFT) is False
    assert is_relevant(C.FINANCES, SHIFT_WITH_APPT) is False


def test_filter_b_ties_personal_care_to_hands_on_shifts():
    assert is_relevant(C.PERSONAL_CARE_LOG, SHIFT) is True
    assert is_relevant(C.PERSONAL_CARE_LOG, SHIFT_NO_CARE) is False


def test_coverage_surface_carries_no_record_content():
    week = RelevanceContext(surface=Surface.COVERAGE)
    assert [c for c in CATEGORY_ORDER if is_relevant(c, week)] == [C.PREFERENCES]


def test_visible_is_the_intersection(fatima):
    got = visible_categories(fatima, SHIFT)
    assert got == {C.MEDS_SCHEDULE, C.PREFERENCES, C.PERSONAL_CARE_LOG}
    assert C.MOOD_NOTES not in got       # blocked by Filter A
    assert C.APPOINTMENTS not in got     # blocked by Filter B
    assert C.FINANCES not in got         # blocked by both


def test_close_family_sees_mood_notes_on_the_same_shift(omar):
    """Same screen, same code, different column: the contrast that shows the
    grid is doing the work and the job title is not."""
    assert C.MOOD_NOTES in visible_categories(omar, SHIFT)
    assert C.MOOD_NOTES not in visible_categories(omar, SHIFT_NO_CARE)


def test_permission_beats_relevance_when_reporting_a_block(fatima):
    """A caregiver must not learn that mood notes exist. Filter A wins."""
    assert blocked_by(fatima, C.MOOD_NOTES, SHIFT) == BlockedBy.PERMISSION
    assert blocked_by(fatima, C.APPOINTMENTS, SHIFT) == BlockedBy.RELEVANCE
    assert blocked_by(fatima, C.MEDS_SCHEDULE, SHIFT) == BlockedBy.NOTHING


def test_only_permitted_categories_are_ever_named_as_withheld(fatima):
    withheld = withheld_as_irrelevant(fatima, SHIFT)
    assert withheld == {C.APPOINTMENTS}
    assert C.MOOD_NOTES not in withheld
    assert C.FINANCES not in withheld


def test_visiting_relative_gets_almost_nothing_on_a_shift(sara):
    assert granted(sara) == {C.APPOINTMENTS, C.PREFERENCES}
    assert visible_categories(sara, SHIFT) == {C.PREFERENCES}


@pytest.mark.parametrize("category", list(CATEGORY_ORDER))
def test_no_category_escapes_both_filters(fatima, category):
    visible = visible_categories(fatima, SHIFT)
    expected = has_permission(fatima, category) and is_relevant(category, SHIFT)
    assert (category in visible) is expected
