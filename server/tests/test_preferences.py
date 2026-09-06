"""Preferences: the parsing rules, and the two wired consequences.

A preference form that changes nothing on screen is a settings page with extra
steps. These two tests are the ones that stop that happening.
"""
from __future__ import annotations

import pytest

from app.domain.preferences import (
    Preferences,
    apply_prayer_buffer,
    check_bathing_assignment,
    hhmm,
    minutes,
)


def prefs(**over):
    base = {
        "caregiver_gender": {"bathing": "any", "meals": "any", "transport": "any"},
        "prayer_times": {"method": "ISNA", "buffer_min": 0, "fajr": "05:40"},
        "diet": {"meat": "any"},
        "language": {},
    }
    base.update(over)
    return Preferences.from_dict(base)


# --- consequence 1: the buffer moves a time on the caregiver's screen ------

def test_the_buffer_pushes_a_dose_out_of_the_prayer_window():
    """Fajr 05:40, 20 minutes clear, dose entered for 05:45 -> shown at 06:00.
    This is the number from the demo script."""
    p = prefs(prayer_times={"fajr": "05:40", "buffer_min": 20})
    shift = apply_prayer_buffer("05:45", p)
    assert shift.display_time == "06:00"
    assert shift.shifted is True
    assert shift.shifted_by_min == 15
    assert "Fajr" in shift.reason and "05:45" in shift.reason


def test_a_bigger_buffer_moves_it_further():
    p = prefs(prayer_times={"fajr": "05:40", "buffer_min": 45})
    assert apply_prayer_buffer("05:45", p).display_time == "06:25"


def test_no_buffer_means_no_change():
    assert apply_prayer_buffer("05:45", prefs()).display_time == "05:45"
    assert apply_prayer_buffer("05:45", prefs()).shifted is False


def test_a_dose_outside_every_window_is_untouched():
    p = prefs(prayer_times={"fajr": "05:40", "buffer_min": 20})
    assert apply_prayer_buffer("08:00", p).display_time == "08:00"


def test_a_dose_exactly_at_the_end_of_the_window_is_untouched():
    p = prefs(prayer_times={"fajr": "05:40", "buffer_min": 20})
    assert apply_prayer_buffer("06:00", p).shifted is False


def test_the_buffer_only_moves_when_the_dose_is_offered_not_what_it_is():
    """The one clinical guardrail in the codebase: this function may return a
    different time and nothing else."""
    p = prefs(prayer_times={"fajr": "05:40", "buffer_min": 20})
    result = apply_prayer_buffer("05:45", p)
    assert set(vars(result)) == {"display_time", "shifted", "shifted_by_min", "reason"}


# --- consequence 2: bathing gender warns on assignment ---------------------

def test_a_bathing_shift_staffed_against_the_preference_warns():
    p = prefs(caregiver_gender={"bathing": "female"})
    check = check_bathing_assignment(p, "male", shift_includes_personal_care=True)
    assert check.ok is False
    assert "female" in check.warning.lower()


def test_a_matching_caregiver_does_not_warn():
    p = prefs(caregiver_gender={"bathing": "female"})
    assert check_bathing_assignment(p, "female", True).ok is True


def test_no_warning_when_the_shift_has_no_personal_care_on_it():
    p = prefs(caregiver_gender={"bathing": "female"})
    assert check_bathing_assignment(p, "male", False).ok is True


def test_no_preference_means_no_warning():
    assert check_bathing_assignment(prefs(), "male", True).ok is True


def test_an_unrecorded_gender_warns_rather_than_passing_silently():
    p = prefs(caregiver_gender={"bathing": "female"})
    check = check_bathing_assignment(p, "unspecified", True)
    assert check.ok is False
    assert "not recorded" in check.warning


# --- the enum-vs-text rule ------------------------------------------------

def test_unknown_enum_values_fall_back_instead_of_being_stored():
    p = Preferences.from_dict({"diet": {"meat": "whatever"}, "caregiver_gender": {"bathing": "yes"}})
    assert p.diet.meat == "any"
    assert p.caregiver_gender.bathing == "any"


def test_free_text_is_kept_verbatim():
    p = Preferences.from_dict({"diet": {"meat": "other", "meat_other": "No beef; she cannot digest it"}})
    assert p.diet.meat_other == "No beef; she cannot digest it"


def test_there_is_no_muslim_friendly_flag_anywhere():
    """Every cultural preference is an individual field with its own value."""
    fields = set(Preferences().to_dict())
    assert fields == {"caregiver_gender", "prayer_times", "diet", "language", "notes"}
    flat = str(Preferences().to_dict()).lower()
    for word in ["muslim", "islamic", "religious_mode", "culturally"]:
        assert word not in flat


def test_the_buffer_is_clamped_to_something_sane():
    assert Preferences.from_dict({"prayer_times": {"buffer_min": 9999}}).prayer_times.buffer_min == 180
    assert Preferences.from_dict({"prayer_times": {"buffer_min": -5}}).prayer_times.buffer_min == 0
    assert Preferences.from_dict({"prayer_times": {"buffer_min": "abc"}}).prayer_times.buffer_min == 0


def test_a_malformed_time_falls_back_to_the_default():
    assert Preferences.from_dict({"prayer_times": {"fajr": "25:99"}}).prayer_times.fajr == "05:40"
    assert Preferences.from_dict({"prayer_times": {"fajr": "banana"}}).prayer_times.fajr == "05:40"


def test_a_round_trip_through_the_dict_form_is_lossless():
    original = Preferences.from_dict({
        "caregiver_gender": {"bathing": "female", "meals": "male", "transport": "any"},
        "prayer_times": {"method": "MWL", "buffer_min": 20, "fajr": "05:12"},
        "diet": {"meat": "zabiha_only", "seafood": "restricted", "substitutes": ["Tuna"]},
        "language": {"spoken": "Somali", "written": "Somali"},
        "notes": "Ask twice.",
    })
    assert Preferences.from_dict(original.to_dict()).to_dict() == original.to_dict()


@pytest.mark.parametrize("value", [0, 61, 1439])
def test_minutes_and_hhmm_are_inverses(value):
    assert minutes(hhmm(value)) == value
