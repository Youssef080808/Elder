"""The caregiver's screens: the shift card and the week's coverage.

The shift card is the endpoint that matters. Its response is assembled by
`care_view`, which is the only place that decides what a caregiver sees, and a
category blocked by the elder is absent from the JSON entirely -- not sent with
a flag for the browser to respect.
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException

from app.services import care_view, coverage
from app.api.deps import db_session, elder_of_record, require_person

router = APIRouter(prefix="/api", tags=["caregiver"])


@router.get("/shift")
def current_shift(
    db=Depends(db_session), person=Depends(require_person), elder=Depends(elder_of_record)
):
    """Pushed, not searched.

    Permissions are re-checked here on every request, not at sign-in, so a
    revocation lands on the caregiver's next screen without them signing out.
    """
    shift = coverage.current_shift(db, caregiver=person)
    if shift is None:
        return {"card": None, "upcoming": []}
    card = care_view.build_shift_card(db, shift=shift, viewer=person, elder=elder)
    return {
        "card": card.to_dict(),
        "upcoming": [
            {"id": s.id, "date": s.date.isoformat(), "start": s.start, "end": s.end, "label": s.label}
            for s in coverage.shifts_for(db, caregiver=person)
        ],
    }


@router.get("/shift/{shift_id}")
def one_shift(
    shift_id: str,
    db=Depends(db_session),
    person=Depends(require_person),
    elder=Depends(elder_of_record),
):
    shift = _own_shift(db, shift_id, person)
    card = care_view.build_shift_card(db, shift=shift, viewer=person, elder=elder)
    return {"card": card.to_dict()}


@router.post("/shift/{shift_id}/medication")
def mark_given(
    shift_id: str,
    medication_id: str = Body(..., embed=True),
    db=Depends(db_session),
    person=Depends(require_person),
    elder=Depends(elder_of_record),
):
    """Records that a person gave a dose. The app makes no clinical judgement:
    it stores who pressed the button and when."""
    shift = _own_shift(db, shift_id, person)
    given = care_view.mark_med_given(
        db, shift=shift, medication_id=medication_id, viewer=person, elder=elder
    )
    if given is None:
        raise HTTPException(403, "That medication is not part of what you can see.")
    card = care_view.build_shift_card(
        db, shift=shift, viewer=person, elder=elder, log_disclosure=False
    )
    return {"card": card.to_dict()}


@router.post("/shift/{shift_id}/handoff")
def leave_handoff(
    shift_id: str,
    text: str = Body(..., embed=True),
    db=Depends(db_session),
    person=Depends(require_person),
    elder=Depends(elder_of_record),
):
    shift = _own_shift(db, shift_id, person)
    note = care_view.write_handoff(db, shift=shift, viewer=person, elder=elder, text=text)
    if note is None:
        raise HTTPException(403, "You cannot leave a handoff note on this shift.")
    card = care_view.build_shift_card(
        db, shift=shift, viewer=person, elder=elder, log_disclosure=False
    )
    return {"card": card.to_dict()}


@router.get("/coverage")
def week(db=Depends(db_session), person=Depends(require_person), elder=Depends(elder_of_record)):
    """Seven rows. A group chat cannot show that nobody is covering Thursday."""
    return coverage.to_dict(coverage.week_coverage(db, elder=elder, viewer=person))


@router.get("/search")
def search(person=Depends(require_person)):
    """Deliberately not built, and honest about it.

    A caregiver arriving at six in the morning does not know what to search
    for -- not knowing what you don't know is the actual handoff failure -- so
    the shift card pushes and search is only ever the escape hatch. When it
    exists it will answer through the same two filters, so it cannot become a
    way around the grid.
    """
    return {
        "available": False,
        "message": (
            "Search is reserved for the next release. Your shift card is the "
            "source of truth for now."
        ),
    }


def _own_shift(db, shift_id: str, person):
    """Ownership check: separate from, and prior to, the two visibility
    filters. A caregiver may only open their own shift."""
    shift = coverage.shift_by_id(db, shift_id=shift_id, caregiver=person)
    if shift is None:
        raise HTTPException(404, "That shift is not yours.")
    return shift
