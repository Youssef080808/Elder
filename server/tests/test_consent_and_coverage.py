"""Presets and column divergence; the week view and its gaps."""
from __future__ import annotations

from sqlalchemy import select

from app.domain.categories import CATEGORY_ORDER, DataCategory as C, Preset, preset_grants
from app.models import Shift
from app.services import consent, coverage
from tests.conftest import granted, sign_in


def test_the_three_presets_are_exactly_what_the_spec_says():
    assert preset_grants(Preset.CLOSE_FAMILY) == frozenset(CATEGORY_ORDER)
    assert preset_grants(Preset.PAID_CAREGIVER) == {
        C.MEDS_SCHEDULE, C.APPOINTMENTS, C.PREFERENCES, C.PERSONAL_CARE_LOG
    }
    assert preset_grants(Preset.VISITING_RELATIVE) == {C.APPOINTMENTS, C.PREFERENCES}
    assert len(list(Preset)) == 3


def test_a_preset_stamps_values_that_then_diverge(db, elder, fatima):
    assert granted(fatima) == preset_grants(Preset.PAID_CAREGIVER)
    consent.set_permission(
        db, elder_id=elder.id, actor=elder, target=fatima,
        category=C.PERSONAL_CARE_LOG, granted=False,
    )
    assert granted(fatima) == {C.MEDS_SCHEDULE, C.APPOINTMENTS, C.PREFERENCES}
    assert granted(fatima) != preset_grants(Preset.PAID_CAREGIVER)


def test_stamping_one_column_leaves_every_other_column_alone(db, elder, fatima, omar, sara):
    before = {omar.id: granted(omar), sara.id: granted(sara)}
    consent.apply_preset(
        db, elder_id=elder.id, actor=elder, target=fatima, preset=Preset.CLOSE_FAMILY
    )
    assert granted(omar) == before[omar.id]
    assert granted(sara) == before[sara.id]


def test_every_person_carries_a_row_per_category(db, fatima):
    assert {p.category for p in fatima.permissions} == {c.value for c in CATEGORY_ORDER}


def test_a_repeat_toggle_writes_no_second_log_entry(db, elder, fatima):
    from app.services.activity import activity_for

    consent.set_permission(
        db, elder_id=elder.id, actor=elder, target=fatima, category=C.MOOD_NOTES, granted=False
    )
    before = len(activity_for(db, elder.id, elder))
    consent.set_permission(
        db, elder_id=elder.id, actor=elder, target=fatima, category=C.MOOD_NOTES, granted=False
    )
    assert len(activity_for(db, elder.id, elder)) == before


def test_there_is_no_share_everything_endpoint(client, db, elder):
    """The product claim is that no global state exists. This asserts it at the
    HTTP surface, not just in prose."""
    from app.main import app

    for route in app.routes:
        path = getattr(route, "path", "")
        assert "share" not in path
        assert "all" not in path.split("/")


def test_the_grid_marks_dignity_sensitive_rows(client, db, elder):
    sign_in(client, elder)
    grid = client.get("/api/elder/permissions").json()
    sensitive = {c["key"] for c in grid["categories"] if c["dignity_sensitive"]}
    assert sensitive == {"personal_care_log", "mood_notes", "finances"}


def test_grid_locks_match_the_server_rule(client, db, elder, omar, fatima):
    from app.services import delegation

    delegation.appoint_proxy(db, elder=elder, actor=elder, target=omar)
    sign_in(client, omar)
    grid = client.get("/api/elder/permissions").json()
    own = next(c for c in grid["columns"] if c["person"]["id"] == omar.id)
    other = next(c for c in grid["columns"] if c["person"]["id"] == fatima.id)
    assert all(cell["locked"] for cell in own["cells"])
    assert not any(cell["locked"] for cell in other["cells"])


# --- coverage --------------------------------------------------------------

def test_an_unstaffed_shift_shows_even_on_a_day_with_other_cover(db, elder):
    week = coverage.week_coverage(db, elder=elder, viewer=elder)
    assert week.open_shift_count >= 1
    day_with_open = next(d for d in week.days if d.open_shifts)
    assert day_with_open.needs_attention is True


def test_a_bathing_shift_against_the_preference_is_flagged(db, elder):
    """Omar covers an evening that includes personal care, and Amira has asked
    for a woman for bathing. That row lights up."""
    week = coverage.week_coverage(db, elder=elder, viewer=elder)
    flagged = [row for day in week.days for row in day.shifts if row.warning]
    assert flagged
    assert flagged[0].caregiver_name == "Omar Hassan"
    assert flagged[0].shift.includes_personal_care is True


def test_no_warning_once_the_preference_allows_it(db, elder):
    from app.services.people import load_preferences, save_preferences

    prefs = load_preferences(db, elder.id)
    prefs.caregiver_gender.bathing = "any"
    save_preferences(db, elder.id, prefs)
    assert coverage.week_coverage(db, elder=elder, viewer=elder).warning_count == 0


def test_assigning_a_caregiver_closes_a_gap(db, elder, fatima):
    before = coverage.week_coverage(db, elder=elder, viewer=elder).open_shift_count
    gap = db.execute(select(Shift).where(Shift.covered.is_(False))).scalars().first()
    assert coverage.assign_shifts(db, caregiver=fatima, shift_ids=[gap.id]) == 1
    db.commit()
    assert coverage.week_coverage(db, elder=elder, viewer=elder).open_shift_count == before - 1


def test_an_already_covered_shift_is_not_reassigned(db, elder, fatima, omar):
    taken = db.execute(select(Shift).where(Shift.caregiver_id == omar.id)).scalars().first()
    assert coverage.assign_shifts(db, caregiver=fatima, shift_ids=[taken.id]) == 0
    assert taken.caregiver_id == omar.id


def test_workload_counts_hours_from_the_rota(db, elder):
    rows = coverage.workload(db, elder=elder)
    fatima = next(r for r in rows if r["id"] == "fatima")
    assert fatima["shifts"] >= 3
    assert fatima["hours"] == fatima["shifts"] * 8  # 06:00-14:00
