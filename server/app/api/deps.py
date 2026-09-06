"""Request-scoped wiring: who is signed in, and how a refusal is reported.

Route modules deliberately import nothing from `app.models` and nothing from
SQLAlchemy. They receive a Person and a Session from here and then talk only to
services, so no route in this codebase can query a category table directly.
`tests/test_architecture.py` enforces that mechanically.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from app.config import SESSION_COOKIE
from app.db import get_db
from app.domain.proxy import is_active_proxy
from app.services.people import get_person, the_elder


def db_session(db=Depends(get_db)):
    return db


def current_person(request: Request, db=Depends(get_db)):
    """The demo's stand-in for authentication.

    In production a person signs in as themselves and their role comes from
    their record. Nothing downstream would change: the permission engine never
    trusts the client for anything but identity.
    """
    return get_person(db, request.cookies.get(SESSION_COOKIE))


def require_person(person=Depends(current_person)):
    if person is None:
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    return person


def require_elder_or_proxy(person=Depends(require_person)):
    """The grid is the elder's screen. An active proxy stands in it on her
    behalf, and every action they take there is logged as such."""
    if person.role == "elder" or is_active_proxy(person):
        return person
    raise HTTPException(status_code=403, detail="Only Amira or her proxy can do this.")


def require_elder_only(person=Depends(require_person)):
    if person.role != "elder":
        raise HTTPException(
            status_code=403,
            detail="Only the elder can do this. A proxy cannot appoint another proxy.",
        )
    return person


def elder_of_record(db=Depends(get_db)):
    return the_elder(db)


def person_payload(person, *, is_proxy: bool = False) -> dict:
    return {
        "id": person.id,
        "name": person.name,
        "first_name": person.name.split(" ")[0],
        "role": person.role,
        "role_label": person.role_label,
        "initials": person.initials,
        "tone": person.tone,
        "gender": person.gender,
        "is_proxy": is_proxy,
    }
