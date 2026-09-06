"""Sign in and sign out. A demo affordance, not authentication."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Response

from app.config import SESSION_COOKIE
from app.domain.proxy import is_active_proxy
from app.services import people
from app.api.deps import current_person, db_session, elder_of_record, person_payload

router = APIRouter(prefix="/api/session", tags=["session"])


@router.get("")
def whoami(person=Depends(current_person), elder=Depends(elder_of_record), db=Depends(db_session)):
    """Who is signed in, and who else is in the circle. Never any record
    content -- this is the sign-in screen's data, not a profile."""
    return {
        "signed_in": person is not None,
        "person": person_payload(person, is_proxy=is_active_proxy(person)) if person else None,
        "elder": person_payload(elder),
        "circle": [
            person_payload(p, is_proxy=is_active_proxy(p))
            for p in people.circle(db, elder.id)
        ],
    }


@router.post("/login")
def login(response: Response, person_id: str = Body(..., embed=True), db=Depends(db_session)):
    chosen = people.get_person(db, person_id)
    if chosen is None:
        raise HTTPException(404, "No such person.")
    response.set_cookie(SESSION_COOKIE, chosen.id, httponly=True, samesite="lax")
    return {
        "person": person_payload(chosen, is_proxy=is_active_proxy(chosen)),
        "landing": "overview" if chosen.role == "elder" else "shift",
    }


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE)
    return {"signed_in": False}
