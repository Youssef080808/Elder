"""Every delegation rule, one test each, exercised through the HTTP API.

The rules exist because financial exploitation of elders is overwhelmingly
committed by family members. A single toggle that hands a relative everything
including the money would build the shape of the problem.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.config import PROXY_TERM_DAYS
from app.domain.categories import DataCategory as C, Preset
from app.domain.proxy import ProxyViolation, is_active_proxy
from app.services import consent, delegation
from app.services.activity import activity_for
from tests.conftest import granted, refresh, sign_in


def test_elder_appoints_and_proxy_gets_the_widest_preset_minus_money(db, elder, omar):
    delegation.appoint_proxy(db, elder=elder, actor=elder, target=omar)
    assert is_active_proxy(omar)
    assert granted(omar) == {
        C.MEDS_SCHEDULE, C.APPOINTMENTS, C.PREFERENCES, C.PERSONAL_CARE_LOG, C.MOOD_NOTES
    }
    assert C.FINANCES not in granted(omar)


def test_at_most_one_proxy_at_a_time(db, elder, omar, sara):
    delegation.appoint_proxy(db, elder=elder, actor=elder, target=omar)
    delegation.appoint_proxy(db, elder=elder, actor=elder, target=sara)
    assert is_active_proxy(sara)
    assert not is_active_proxy(omar)
    assert delegation.proxy_status(db, elder.id)[0].id == sara.id


def test_a_proxy_cannot_appoint_another_proxy(db, elder, omar, sara):
    delegation.appoint_proxy(db, elder=elder, actor=elder, target=omar)
    with pytest.raises(ProxyViolation):
        delegation.appoint_proxy(db, elder=elder, actor=omar, target=sara)


def test_a_proxy_cannot_widen_their_own_access(db, elder, omar):
    delegation.appoint_proxy(db, elder=elder, actor=elder, target=omar)
    with pytest.raises(ProxyViolation):
        consent.set_permission(
            db, elder_id=elder.id, actor=omar, target=omar, category=C.FINANCES, granted=True
        )
    assert C.FINANCES not in granted(omar)


def test_a_proxy_manages_everyone_elses_column(db, elder, omar, fatima):
    delegation.appoint_proxy(db, elder=elder, actor=elder, target=omar)
    consent.set_permission(
        db, elder_id=elder.id, actor=omar, target=fatima, category=C.MOOD_NOTES, granted=True
    )
    assert C.MOOD_NOTES in granted(fatima)


def test_presets_never_hand_a_proxy_the_money(db, elder, omar):
    """Not even the widest one, stamped by the elder herself."""
    delegation.appoint_proxy(db, elder=elder, actor=elder, target=omar)
    consent.apply_preset(
        db, elder_id=elder.id, actor=elder, target=omar, preset=Preset.CLOSE_FAMILY
    )
    assert C.FINANCES not in granted(omar)


def test_finances_can_still_be_granted_deliberately_by_the_elder(db, elder, omar):
    delegation.appoint_proxy(db, elder=elder, actor=elder, target=omar)
    consent.set_permission(
        db, elder_id=elder.id, actor=elder, target=omar, category=C.FINANCES, granted=True
    )
    assert C.FINANCES in granted(omar)


def test_delegation_is_time_bounded(db, elder, omar):
    delegation.appoint_proxy(db, elder=elder, actor=elder, target=omar)
    assert omar.proxy_expires_at is not None
    assert delegation.days_remaining(omar.proxy_expires_at) in (PROXY_TERM_DAYS - 1, PROXY_TERM_DAYS)


def test_an_expired_proxy_loses_authority_but_keeps_their_own_column(db, elder, omar, fatima):
    delegation.appoint_proxy(db, elder=elder, actor=elder, target=omar)
    omar.proxy_expires_at = datetime.utcnow() - timedelta(days=1)
    db.commit()
    assert not is_active_proxy(omar)
    assert C.MOOD_NOTES in granted(omar)
    with pytest.raises(ProxyViolation):
        consent.set_permission(
            db, elder_id=elder.id, actor=omar, target=fatima, category=C.FINANCES, granted=True
        )


def test_revocation_ends_authority_and_leaves_access_alone(db, elder, omar):
    delegation.appoint_proxy(db, elder=elder, actor=elder, target=omar)
    before = granted(omar)
    delegation.revoke_proxy(db, elder=elder, actor=elder)
    assert not is_active_proxy(omar)
    assert granted(omar) == before


def test_only_the_elder_can_revoke(db, elder, omar, fatima):
    delegation.appoint_proxy(db, elder=elder, actor=elder, target=omar)
    with pytest.raises(ProxyViolation):
        delegation.revoke_proxy(db, elder=elder, actor=fatima)


def test_proxy_actions_are_visible_to_every_family_member(db, elder, omar, sara, fatima):
    """Visibility to the family is the safeguard on delegation, not
    restriction of the proxy."""
    delegation.appoint_proxy(db, elder=elder, actor=elder, target=omar)
    consent.set_permission(
        db, elder_id=elder.id, actor=omar, target=fatima, category=C.MOOD_NOTES, granted=True
    )
    seen = [row.text for row in activity_for(db, elder.id, sara)]
    assert any("acting as proxy" in text for text in seen)
    assert any("Fatima" in text and "mood notes" in text for text in seen)


def test_proxy_entries_read_as_acting_for_the_elder(db, elder, omar, fatima):
    delegation.appoint_proxy(db, elder=elder, actor=elder, target=omar)
    consent.set_permission(
        db, elder_id=elder.id, actor=omar, target=fatima, category=C.MOOD_NOTES, granted=True
    )
    rows = activity_for(db, elder.id, elder)
    assert rows[0].acting_as_proxy is True
    assert rows[0].text.startswith("Omar Hassan, acting as proxy,")


# --- the same rules, over HTTP, with the UI bypassed entirely --------------

def test_the_rule_is_enforced_by_the_server_not_by_hiding_the_button(client, db, elder, omar):
    delegation.appoint_proxy(db, elder=elder, actor=elder, target=omar)
    sign_in(client, omar)
    response = client.post(
        "/api/elder/permissions/toggle",
        json={"person_id": omar.id, "category": "finances", "granted": True},
    )
    assert response.status_code == 403
    assert "cannot change their own access" in response.json()["detail"]
    refresh(db)
    assert C.FINANCES not in granted(omar)


def test_a_proxy_cannot_appoint_over_http(client, db, elder, omar, sara):
    delegation.appoint_proxy(db, elder=elder, actor=elder, target=omar)
    sign_in(client, omar)
    response = client.post("/api/elder/proxy", json={"person_id": sara.id})
    assert response.status_code == 403
    assert "cannot appoint another proxy" in response.json()["detail"]


def test_a_paid_caregiver_cannot_touch_the_grid_at_all(client, db, elder, fatima):
    sign_in(client, fatima)
    response = client.post(
        "/api/elder/permissions/toggle",
        json={"person_id": fatima.id, "category": "finances", "granted": True},
    )
    assert response.status_code == 403
    refresh(db)
    assert C.FINANCES not in granted(fatima)


def test_a_proxy_can_still_do_the_job_over_http(client, db, elder, omar, fatima):
    delegation.appoint_proxy(db, elder=elder, actor=elder, target=omar)
    sign_in(client, omar)
    response = client.post(
        "/api/elder/permissions/toggle",
        json={"person_id": fatima.id, "category": "mood_notes", "granted": True},
    )
    assert response.status_code == 200
    refresh(db)
    assert C.MOOD_NOTES in granted(fatima)
