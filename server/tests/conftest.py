"""Test fixtures.

Every test runs against a freshly seeded SQLite file, which is what the
deployment does on boot. There are no mocks of the permission engine anywhere
in this suite: when a test says a caregiver cannot see mood notes, that is the
real engine saying so.
"""
from __future__ import annotations

import os
import tempfile

import pytest

_TMP_DB = os.path.join(tempfile.gettempdir(), "carecircle_test.db")
os.environ["DATABASE_URL"] = "sqlite:///{}".format(_TMP_DB)
os.environ["RESEED_ON_BOOT"] = "0"  # the db fixture owns seeding

from fastapi.testclient import TestClient  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.domain.categories import DataCategory  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import reset_database, seed  # noqa: E402
from app.services import people  # noqa: E402


@pytest.fixture
def db():
    reset_database()
    session = SessionLocal()
    seed(session)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def elder(db):
    return people.the_elder(db)


@pytest.fixture
def fatima(db, elder):
    return _by_id(db, elder, "fatima")


@pytest.fixture
def omar(db, elder):
    return _by_id(db, elder, "omar")


@pytest.fixture
def sara(db, elder):
    return _by_id(db, elder, "sara")


@pytest.fixture
def client(db):
    with TestClient(app) as test_client:
        yield test_client


def sign_in(client, person):
    response = client.post("/api/session/login", json={"person_id": person.id})
    assert response.status_code == 200
    return client


def refresh(db):
    """Let the fixture session see writes made by a request's own session."""
    db.commit()
    db.expire_all()


def granted(person):
    return {DataCategory(p.category) for p in person.permissions if p.granted}


def _by_id(db, elder, person_id):
    for person in people.circle(db, elder.id):
        if person.id == person_id:
            return person
    raise AssertionError("{} is not in the seeded circle".format(person_id))
