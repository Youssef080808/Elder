"""The reason this backend exists.

The front end used to hold the whole record in localStorage and decide what to
draw. These tests assert the property that replaces it: a category the elder
has not shared is absent from the JSON on the wire, so there is nothing for
devtools to find and nothing for a client bug to reveal.
"""
from __future__ import annotations

import json

from sqlalchemy import select

from app.domain.categories import DataCategory as C
from app.models import HandoffNote, MedAdministration, Medication, Shift
from app.services import care_view, consent
from tests.conftest import refresh, sign_in


BLOCKED_STRINGS = [
    "Quiet after the call",   # the mood note
    "820",                    # the direct debit
    "State pension",
    "Cardiology",             # an appointment outside the shift window
]


def test_a_blocked_category_has_no_key_in_the_response(client, db, elder, fatima):
    """Not `null`, not `[]`, not a `false` flag the client is trusted to
    respect. The key is not there."""
    sign_in(client, fatima)
    card = client.get("/api/shift").json()["card"]
    assert "mood_notes" not in card
    assert "finances" not in card
    assert "appointments" not in card  # permitted, but not this shift
    assert set(card["visible"]) == {"meds_schedule", "personal_care_log", "preferences"}


def test_blocked_content_never_reaches_the_wire(client, db, elder, fatima):
    sign_in(client, fatima)
    raw = client.get("/api/shift").text
    for probe in BLOCKED_STRINGS:
        assert probe not in raw, "leaked: {}".format(probe)
    assert "mood" not in raw.lower()


def test_every_endpoint_a_caregiver_can_reach_is_clean(client, db, elder, fatima):
    """Sweep the whole surface, not just the shift card."""
    sign_in(client, fatima)
    for path in ["/api/session", "/api/shift", "/api/coverage", "/api/search"]:
        raw = client.get(path).text
        for probe in BLOCKED_STRINGS:
            assert probe not in raw, "{} leaked {}".format(path, probe)


def test_the_elders_own_screens_may_of_course_show_everything(client, db, elder):
    sign_in(client, elder)
    raw = client.get("/api/elder/overview").text
    assert "Metformin" in raw  # her own record, on her own screen


def test_revocation_lands_on_the_next_request_not_the_next_login(client, db, elder, fatima):
    sign_in(client, fatima)
    assert "personal_care" in client.get("/api/shift").json()["card"]

    consent.set_permission(
        db, elder_id=elder.id, actor=elder, target=fatima,
        category=C.PERSONAL_CARE_LOG, granted=False,
    )

    # Same cookie, same session, no sign-out.
    card = client.get("/api/shift").json()["card"]
    assert "personal_care" not in card
    assert "handoff_in" not in card
    assert "medications" in card  # the rest of her shift still works


def test_a_revoked_category_cannot_be_written_to_either(client, db, elder, fatima):
    """The write path re-checks. Hiding a form is not the control."""
    shift = db.execute(
        select(Shift).where(Shift.caregiver_id == fatima.id)
    ).scalars().first()
    consent.set_permission(
        db, elder_id=elder.id, actor=elder, target=fatima,
        category=C.PERSONAL_CARE_LOG, granted=False,
    )
    sign_in(client, fatima)
    response = client.post(
        "/api/shift/{}/handoff".format(shift.id), json={"text": "Should not be stored"}
    )
    assert response.status_code == 403
    refresh(db)
    assert db.execute(
        select(HandoffNote).where(HandoffNote.shift_id == shift.id)
    ).scalars().all() == []


def test_a_caregiver_without_the_meds_column_cannot_record_a_dose(client, db, elder, fatima):
    shift = db.execute(select(Shift).where(Shift.caregiver_id == fatima.id)).scalars().first()
    consent.set_permission(
        db, elder_id=elder.id, actor=elder, target=fatima,
        category=C.MEDS_SCHEDULE, granted=False,
    )
    med = db.execute(select(Medication)).scalars().first()
    sign_in(client, fatima)
    response = client.post(
        "/api/shift/{}/medication".format(shift.id), json={"medication_id": med.id}
    )
    assert response.status_code == 403
    refresh(db)
    assert db.execute(select(MedAdministration)).scalars().all() == []


def test_a_caregiver_cannot_open_someone_elses_shift(client, db, elder, fatima, omar):
    someone_elses = db.execute(
        select(Shift).where(Shift.caregiver_id == omar.id)
    ).scalars().first()
    sign_in(client, fatima)
    assert client.get("/api/shift/{}".format(someone_elses.id)).status_code == 404


def test_a_caregiver_cannot_reach_the_elders_endpoints(client, db, elder, fatima):
    sign_in(client, fatima)
    for path in ["/api/elder/overview", "/api/elder/permissions", "/api/elder/activity",
                 "/api/elder/preferences", "/api/elder/workload",
                 "/api/elder/preview/{}".format(fatima.id)]:
        assert client.get(path).status_code == 403, path


def test_signed_out_requests_get_nothing(client, db):
    for path in ["/api/shift", "/api/coverage", "/api/elder/permissions", "/api/elder/activity"]:
        assert client.get(path).status_code == 401, path


def test_granting_then_revoking_shows_up_as_a_narrowing_in_the_log(client, db, elder, fatima):
    from app.services.activity import activity_for

    sign_in(client, fatima)
    client.get("/api/shift")
    consent.set_permission(
        db, elder_id=elder.id, actor=elder, target=fatima,
        category=C.PERSONAL_CARE_LOG, granted=False,
    )
    client.get("/api/shift")
    refresh(db)

    disclosures = [r for r in activity_for(db, elder.id, elder) if r.kind == "disclosure"]
    assert len(disclosures) == 2
    assert "personal_care_log" in disclosures[-1].categories
    assert "personal_care_log" not in disclosures[0].categories


def test_repeated_polling_does_not_spam_the_elders_log(client, db, elder, fatima):
    """The client re-fetches on every screen change. The log must record what
    changed, not how often the browser asked."""
    from app.services.activity import activity_for

    sign_in(client, fatima)
    for _ in range(6):
        client.get("/api/shift")
    refresh(db)
    disclosures = [r for r in activity_for(db, elder.id, elder) if r.kind == "disclosure"]
    assert len(disclosures) == 1


def test_the_response_is_json_all_the_way_down(client, db, elder, fatima):
    """Guards against a payload that is technically filtered but ships a blob
    the client is expected to parse and trim."""
    sign_in(client, fatima)
    card = client.get("/api/shift").json()["card"]
    dumped = json.dumps(card)
    assert "<script" not in dumped
    assert "localStorage" not in dumped
