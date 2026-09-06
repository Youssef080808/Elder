"""The elder's screens: the grid, preferences, activity, workload, delegation.

No handler here touches the ORM. Each resolves a person, hands the work to a
service, and returns what comes back.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException

from app.domain.categories import (
    CATEGORY_BLURBS,
    CATEGORY_ICONS,
    CATEGORY_LABELS,
    CATEGORY_ORDER,
    CATEGORY_SHORT,
    DIGNITY_SENSITIVE,
    DataCategory,
    PRESET_BLURBS,
    PRESET_LABELS,
    Preset,
)
from app.domain.logbook import LogEntryKind
from app.domain.preferences import Preferences
from app.domain.proxy import ProxyViolation, is_active_proxy
from app.services import activity, care_view, consent, coverage, delegation, people
from app.api.deps import (
    db_session,
    elder_of_record,
    person_payload,
    require_elder_only,
    require_elder_or_proxy,
)

router = APIRouter(prefix="/api/elder", tags=["elder"])


@router.get("/overview")
def overview(
    db=Depends(db_session), actor=Depends(require_elder_or_proxy), elder=Depends(elder_of_record)
):
    """The elder's home screen, assembled in one round trip.

    It includes the caregiver's card as the caregiver would receive it -- built
    by the same function, through the same two filters. That is the strongest
    thing this product does: the elder is shown the truth about what was
    disclosed, not a summary of it that could drift.
    """
    circle = people.circle(db, elder.id)
    grid = consent.build_grid(db, circle, actor)
    proxy, expires = delegation.proxy_status(db, elder.id)
    week = coverage.week_coverage(db, elder=elder, viewer=elder)

    primary = next((p for p in circle if p.role == "caregiver"), None)
    card = None
    if primary is not None:
        shift = coverage.current_shift(db, caregiver=primary)
        if shift is not None:
            card = care_view.build_shift_card(
                db, shift=shift, viewer=primary, elder=elder, log_disclosure=False
            ).to_dict()

    return {
        "elder": person_payload(elder),
        "proxy": person_payload(proxy, is_proxy=True) if proxy else None,
        "proxy_days_left": delegation.days_remaining(expires),
        "stats": {
            "circle_size": len(circle),
            "covered_shifts": sum(len(d["shifts"]) for d in coverage.to_dict(week)["days"]),
            "open_days": week.uncovered_day_count,
            "categories": len(CATEGORY_ORDER),
        },
        "people": [
            {
                "person": person_payload(col.person, is_proxy=col.is_proxy),
                "granted_count": col.granted_count,
                "total": len(CATEGORY_ORDER),
            }
            for col in grid.columns
        ],
        "primary_caregiver": person_payload(primary) if primary else None,
        "primary_card": card,
    }


@router.get("/permissions")
def permission_grid(
    db=Depends(db_session), actor=Depends(require_elder_or_proxy), elder=Depends(elder_of_record)
):
    """One payload that answers: who can see what about me, right now."""
    circle = people.circle(db, elder.id)
    grid = consent.build_grid(db, circle, actor)
    proxy, expires = delegation.proxy_status(db, elder.id)
    return {
        "categories": [
            {
                "key": c.value,
                "label": CATEGORY_LABELS[c],
                "short": CATEGORY_SHORT[c],
                "icon": CATEGORY_ICONS[c],
                "blurb": CATEGORY_BLURBS[c],
                "dignity_sensitive": c in DIGNITY_SENSITIVE,
            }
            for c in CATEGORY_ORDER
        ],
        "columns": [
            {
                "person": person_payload(col.person, is_proxy=col.is_proxy),
                "granted_count": col.granted_count,
                "cells": [
                    {
                        "category": cell.category.value,
                        "granted": cell.granted,
                        "locked": cell.locked,
                        "lock_reason": cell.lock_reason,
                    }
                    for cell in col.cells
                ],
            }
            for col in grid.columns
        ],
        "presets": [
            {"key": p.value, "label": PRESET_LABELS[p], "blurb": PRESET_BLURBS[p]} for p in Preset
        ],
        "proxy": person_payload(proxy, is_proxy=True) if proxy else None,
        "proxy_days_left": delegation.days_remaining(expires),
        "acting_as_proxy": is_active_proxy(actor),
    }


@router.post("/permissions/toggle")
def toggle_permission(
    person_id: str = Body(...),
    category: str = Body(...),
    granted: bool = Body(...),
    db=Depends(db_session),
    actor=Depends(require_elder_or_proxy),
    elder=Depends(elder_of_record),
):
    """One person, one category. There is no bulk endpoint on purpose."""
    target = people.get_person(db, person_id)
    if target is None:
        raise HTTPException(404, "No such person.")
    try:
        consent.set_permission(
            db, elder_id=elder.id, actor=actor, target=target,
            category=_category(category), granted=granted,
        )
    except ProxyViolation as exc:
        raise HTTPException(403, str(exc))
    return permission_grid(db=db, actor=actor, elder=elder)


@router.post("/permissions/preset")
def stamp_preset(
    person_id: str = Body(...),
    preset: str = Body(...),
    db=Depends(db_session),
    actor=Depends(require_elder_or_proxy),
    elder=Depends(elder_of_record),
):
    target = people.get_person(db, person_id)
    if target is None:
        raise HTTPException(404, "No such person.")
    try:
        consent.apply_preset(
            db, elder_id=elder.id, actor=actor, target=target, preset=_preset(preset)
        )
    except ProxyViolation as exc:
        raise HTTPException(403, str(exc))
    return permission_grid(db=db, actor=actor, elder=elder)


@router.get("/preferences")
def read_preferences(
    db=Depends(db_session), actor=Depends(require_elder_or_proxy), elder=Depends(elder_of_record)
):
    return people.load_preferences(db, elder.id).to_dict()


@router.put("/preferences")
def write_preferences(
    payload: dict = Body(...),
    db=Depends(db_session),
    actor=Depends(require_elder_or_proxy),
    elder=Depends(elder_of_record),
):
    """Unknown enum values fall back rather than being stored -- see
    `Preferences.from_dict`. Free text is kept verbatim."""
    prefs = Preferences.from_dict(payload)
    people.save_preferences(db, elder.id, prefs)
    activity.record(
        db, elder_id=elder.id, actor=actor, kind=LogEntryKind.CONSENT, icon="S",
        acting_as_proxy=is_active_proxy(actor),
        action="{} updated Amira's preferences".format(actor.name),
        detail="Bathing: {}. Prayer buffer before medication: {} minutes.".format(
            prefs.caregiver_gender.bathing, prefs.prayer_times.buffer_min
        ),
        categories=[DataCategory.PREFERENCES],
    )
    return prefs.to_dict()


@router.get("/activity")
def activity_log(
    db=Depends(db_session), actor=Depends(require_elder_or_proxy), elder=Depends(elder_of_record)
):
    """What was shown, and what was done. The elder observing her own care."""
    return {
        "rows": [row.to_dict() for row in activity.activity_for(db, elder.id, actor)],
        "circle": [person_payload(p, is_proxy=is_active_proxy(p)) for p in people.circle(db, elder.id)],
    }


@router.get("/workload")
def workload(
    db=Depends(db_session), actor=Depends(require_elder_or_proxy), elder=Depends(elder_of_record)
):
    """Hours and shifts per person this week. Scheduling only: it carries no
    record content, so it needs no category to be visible."""
    return {"people": coverage.workload(db, elder=elder)}


@router.get("/preview/{person_id}")
def preview_as(
    person_id: str,
    db=Depends(db_session),
    actor=Depends(require_elder_or_proxy),
    elder=Depends(elder_of_record),
):
    """Exactly the payload a caregiver's app would receive.

    Same builder, same two filters, no second code path -- which is the proof
    the elder is being shown the truth rather than a mock-up of it. Looking at
    it logs nothing, because nothing was disclosed to them by her looking.
    """
    target = people.get_person(db, person_id)
    if target is None:
        raise HTTPException(404, "No such person.")
    shift = coverage.current_shift(db, caregiver=target)
    if shift is None:
        return {"person": person_payload(target), "card": None}
    card = care_view.build_shift_card(
        db, shift=shift, viewer=target, elder=elder, log_disclosure=False
    )
    return {"person": person_payload(target), "card": card.to_dict()}


@router.post("/proxy")
def appoint(
    person_id: str = Body(..., embed=True),
    db=Depends(db_session),
    actor=Depends(require_elder_only),
    elder=Depends(elder_of_record),
):
    target = people.get_person(db, person_id)
    try:
        delegation.appoint_proxy(db, elder=elder, actor=actor, target=target)
    except ProxyViolation as exc:
        raise HTTPException(403, str(exc))
    return permission_grid(db=db, actor=actor, elder=elder)


@router.delete("/proxy")
def revoke(
    db=Depends(db_session), actor=Depends(require_elder_only), elder=Depends(elder_of_record)
):
    try:
        delegation.revoke_proxy(db, elder=elder, actor=actor)
    except ProxyViolation as exc:
        raise HTTPException(403, str(exc))
    return permission_grid(db=db, actor=actor, elder=elder)


def _category(value: str) -> DataCategory:
    try:
        return DataCategory(value)
    except ValueError:
        raise HTTPException(400, "Unknown data category: {}".format(value))


def _preset(value: str) -> Preset:
    try:
        return Preset(value)
    except ValueError:
        raise HTTPException(400, "Unknown preset: {}".format(value))
