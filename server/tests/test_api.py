"""The endpoints the front end actually calls."""
from __future__ import annotations

from sqlalchemy import select

from app.models import Medication, Shift
from tests.conftest import refresh, sign_in


def test_health_check(client):
    assert client.get("/healthz").json() == {"ok": True}


def test_session_lists_the_circle_without_any_record_content(client, db, elder):
    body = client.get("/api/session").json()
    assert body["signed_in"] is False
    assert body["elder"]["name"] == "Amira Hassan"
    assert {p["id"] for p in body["circle"]} == {"fatima", "omar", "sara"}
    assert "Metformin" not in client.get("/api/session").text


def test_login_sends_each_role_to_its_own_landing(client, db, elder, fatima):
    assert client.post("/api/session/login", json={"person_id": elder.id}).json()["landing"] == "overview"
    assert client.post("/api/session/login", json={"person_id": fatima.id}).json()["landing"] == "shift"


def test_login_as_nobody_is_a_404(client):
    assert client.post("/api/session/login", json={"person_id": "ghost"}).status_code == 404


def test_logout_clears_the_session(client, db, elder):
    sign_in(client, elder)
    client.post("/api/session/logout")
    assert client.get("/api/elder/permissions").status_code == 401


def test_the_grid_payload_has_a_cell_per_person_per_category(client, db, elder):
    sign_in(client, elder)
    grid = client.get("/api/elder/permissions").json()
    assert len(grid["categories"]) == 6
    assert len(grid["columns"]) == 3
    for column in grid["columns"]:
        assert len(column["cells"]) == 6
    assert [p["key"] for p in grid["presets"]] == [
        "close_family", "paid_caregiver", "visiting_relative"
    ]


def test_toggling_returns_the_whole_fresh_grid(client, db, elder, fatima):
    """The client never patches its own copy: it redraws from the answer the
    server just gave, so the two cannot drift."""
    sign_in(client, elder)
    body = client.post(
        "/api/elder/permissions/toggle",
        json={"person_id": fatima.id, "category": "mood_notes", "granted": True},
    ).json()
    column = next(c for c in body["columns"] if c["person"]["id"] == fatima.id)
    assert next(c for c in column["cells"] if c["category"] == "mood_notes")["granted"] is True


def test_an_unknown_category_is_rejected(client, db, elder, fatima):
    sign_in(client, elder)
    response = client.post(
        "/api/elder/permissions/toggle",
        json={"person_id": fatima.id, "category": "everything", "granted": True},
    )
    assert response.status_code == 400


def test_an_unknown_preset_is_rejected(client, db, elder, fatima):
    sign_in(client, elder)
    assert client.post(
        "/api/elder/permissions/preset", json={"person_id": fatima.id, "preset": "all_access"}
    ).status_code == 400


def test_preferences_round_trip(client, db, elder):
    sign_in(client, elder)
    saved = client.put(
        "/api/elder/preferences",
        json={
            "caregiver_gender": {"bathing": "female", "meals": "any", "transport": "any"},
            "prayer_times": {"method": "ISNA", "buffer_min": 30, "fajr": "05:40"},
            "diet": {"meat": "zabiha_only", "substitutes": ["Oat milk"]},
            "language": {"spoken": "Urdu", "written": "English"},
            "notes": "Ask twice.",
        },
    ).json()
    assert saved["prayer_times"]["buffer_min"] == 30
    assert client.get("/api/elder/preferences").json()["diet"]["substitutes"] == ["Oat milk"]


def test_an_unknown_enum_value_falls_back_instead_of_being_stored(client, db, elder):
    sign_in(client, elder)
    saved = client.put(
        "/api/elder/preferences", json={"caregiver_gender": {"bathing": "whoever"}}
    ).json()
    assert saved["caregiver_gender"]["bathing"] == "any"


def test_changing_the_buffer_moves_the_time_on_the_caregivers_card(client, db, elder, fatima):
    """The wired consequence, observed end to end through the API."""
    sign_in(client, fatima)
    before = client.get("/api/shift").json()["card"]["medications"][0]
    assert before["display_time"] == "06:00"

    sign_in(client, elder)
    client.put("/api/elder/preferences", json={
        "caregiver_gender": {"bathing": "female"},
        "prayer_times": {"method": "ISNA", "buffer_min": 45, "fajr": "05:40"},
        "diet": {"meat": "zabiha_only"}, "language": {}, "notes": "",
    })

    sign_in(client, fatima)
    after = client.get("/api/shift").json()["card"]["medications"][0]
    assert after["display_time"] == "06:25"
    assert after["scheduled_time"] == "05:45"  # what the human entered is unchanged
    assert "45-minute buffer after Fajr" in after["shift_reason"]


def test_marking_a_dose_records_it_once(client, db, elder, fatima):
    shift = db.execute(select(Shift).where(Shift.caregiver_id == fatima.id)).scalars().first()
    med = db.execute(select(Medication).where(Medication.name == "Metformin")).scalars().first()
    sign_in(client, fatima)
    first = client.post("/api/shift/{}/medication".format(shift.id), json={"medication_id": med.id})
    second = client.post("/api/shift/{}/medication".format(shift.id), json={"medication_id": med.id})
    assert first.status_code == second.status_code == 200
    given = [m for m in second.json()["card"]["medications"] if m["given"]]
    assert len(given) == 1
    assert given[0]["given_by"] == "Fatima Rahman"


def test_an_empty_handoff_is_refused(client, db, elder, fatima):
    shift = db.execute(select(Shift).where(Shift.caregiver_id == fatima.id)).scalars().first()
    sign_in(client, fatima)
    assert client.post(
        "/api/shift/{}/handoff".format(shift.id), json={"text": "   "}
    ).status_code == 403


def test_the_week_is_seven_rows_with_the_gaps_marked(client, db, elder):
    sign_in(client, elder)
    week = client.get("/api/coverage").json()
    assert len(week["days"]) == 7
    assert week["sees_everything"] is True
    assert week["uncovered_day_count"] >= 1
    assert any(day["is_gap"] for day in week["days"])
    assert any(day["open_shifts"] for day in week["days"])


def test_a_paid_caregiver_sees_only_her_own_shifts_by_name(client, db, elder, fatima):
    sign_in(client, fatima)
    week = client.get("/api/coverage").json()
    assert week["sees_everything"] is False
    names = {s["caregiver_name"] for day in week["days"] for s in day["shifts"]}
    assert names <= {"Fatima Rahman"}
    # but she still sees that a day is unstaffed
    assert week["uncovered_day_count"] >= 1


def test_workload_carries_hours_not_record_content(client, db, elder):
    sign_in(client, elder)
    body = client.get("/api/elder/workload").json()
    assert {p["id"] for p in body["people"]} == {"fatima", "omar", "sara"}
    assert all("hours" in p and "shifts" in p for p in body["people"])
    assert "Metformin" not in client.get("/api/elder/workload").text


def test_the_preview_is_the_caregivers_real_payload(client, db, elder, fatima):
    """Same builder, same two filters, no second code path."""
    sign_in(client, fatima)
    hers = client.get("/api/shift").json()["card"]
    sign_in(client, elder)
    preview = client.get("/api/elder/preview/{}".format(fatima.id)).json()["card"]
    assert sorted(preview.keys()) == sorted(hers.keys())
    assert preview["visible"] == hers["visible"]


def test_previewing_does_not_log_a_disclosure(client, db, elder, fatima):
    """Nothing was disclosed to Fatima by Amira looking at this."""
    from app.services.activity import activity_for

    sign_in(client, elder)
    before = len(activity_for(db, elder.id, elder))
    client.get("/api/elder/preview/{}".format(fatima.id))
    refresh(db)
    assert len(activity_for(db, elder.id, elder)) == before


def test_preview_of_someone_with_no_shift(client, db, elder, sara):
    sign_in(client, elder)
    body = client.get("/api/elder/preview/{}".format(sara.id)).json()
    assert body["person"]["id"] == sara.id


def test_search_is_honest_about_not_existing(client, db, elder, fatima):
    sign_in(client, fatima)
    body = client.get("/api/search").json()
    assert body["available"] is False


def test_the_activity_log_shows_what_was_shown_and_what_was_done(client, db, elder, fatima):
    shift = db.execute(select(Shift).where(Shift.caregiver_id == fatima.id)).scalars().first()
    med = db.execute(select(Medication).where(Medication.name == "Metformin")).scalars().first()
    sign_in(client, fatima)
    client.get("/api/shift")
    client.post("/api/shift/{}/medication".format(shift.id), json={"medication_id": med.id})
    client.post("/api/shift/{}/handoff".format(shift.id), json={"text": "Took tablets with tea."})

    sign_in(client, elder)
    rows = client.get("/api/elder/activity").json()["rows"]
    texts = [r["text"] for r in rows]
    assert any("was shown" in t and "medication schedule" in t for t in texts)
    assert any("marked Metformin as given" in t for t in texts)
    assert any("left a handoff note" in t for t in texts)
    assert not any("mood notes" in t for t in texts)


def test_the_demo_reset_rebuilds_the_seeded_state(client, db, elder, fatima):
    sign_in(client, elder)
    client.post(
        "/api/elder/permissions/toggle",
        json={"person_id": fatima.id, "category": "mood_notes", "granted": True},
    )
    assert client.post("/api/demo/reset").json() == {"reset": True}
    sign_in(client, elder)
    grid = client.get("/api/elder/permissions").json()
    column = next(c for c in grid["columns"] if c["person"]["id"] == "fatima")
    assert next(c for c in column["cells"] if c["category"] == "mood_notes")["granted"] is False
