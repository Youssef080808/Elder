"""CareCircle API.

Layering, top to bottom:

    app/api/routes_*.py   HTTP wiring only. No ORM, no visibility decisions.
    app/services/*.py     Assemble payloads; every one asks the engine.
    app/domain/*.py       Permission engine, preferences, delegation rules.
                          Pure functions, no database.
    app/models.py         SQLAlchemy tables.

The arrow points one way. `tests/test_architecture.py` fails the build if a
route reaches past a service into the ORM.

Why this exists: the front end used to hold the elder's whole record in
localStorage and decide what to draw. That makes every permission cosmetic --
anyone with devtools can read what she chose not to share. The server now
decides, and a blocked category never leaves the database.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import ALLOWED_ORIGINS, FRONTEND_DIST, FRONTEND_SRC, RESEED_ON_BOOT
from app.db import Base, SessionLocal, engine
from app.api import routes_caregiver, routes_demo, routes_elder, routes_session


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Reseeding on boot is the deliberate hackathon tradeoff: no volume to
    mount, no migrations, and every demo starts from a known state. Set
    RESEED_ON_BOOT=0 with a mounted volume to keep data between deploys."""
    from sqlalchemy import select

    from app.models import Person
    from app.seed import reseed

    Base.metadata.create_all(bind=engine)
    if RESEED_ON_BOOT:
        reseed()
    else:
        db = SessionLocal()
        try:
            if db.execute(select(Person)).scalars().first() is None:
                reseed()
        finally:
            db.close()
    yield


app = FastAPI(title="CareCircle API", lifespan=lifespan)

# Vite serves the front end on :5173 in development and proxies /api here.
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_session.router)
app.include_router(routes_elder.router)
app.include_router(routes_caregiver.router)
app.include_router(routes_demo.router)


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.exception_handler(403)
async def forbidden(request: Request, exc):
    """A refused action explains itself. Most 403s here are delegation rules,
    and the person who hit one should be told which rule stopped them."""
    return JSONResponse(
        {"error": "forbidden", "detail": getattr(exc, "detail", "Not allowed.")}, status_code=403
    )


# Serve the built front end when it exists, so one process runs the whole demo.
_static_root = FRONTEND_DIST if FRONTEND_DIST.is_dir() else FRONTEND_SRC
if _static_root.is_dir():  # pragma: no cover - deployment convenience
    app.mount("/", StaticFiles(directory=str(_static_root), html=True), name="frontend")
