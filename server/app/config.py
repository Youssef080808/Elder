"""Deployment knobs, kept in one place."""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./carecircle.db")

#: Reseeding on boot keeps the demo deterministic and needs no volume.
RESEED_ON_BOOT = os.environ.get("RESEED_ON_BOOT", "1") == "1"

#: Delegation is time-bounded by default.
PROXY_TERM_DAYS = int(os.environ.get("PROXY_TERM_DAYS", "90"))

#: Demo sign-in cookie. This is a demo affordance, not authentication; the
#: security surface of this app is the server-side permission engine.
SESSION_COOKIE = "carecircle_person"

#: In production the API also serves the built front end. In development Vite
#: serves it on :5173 and proxies /api here (see ElderApp/vite.config.js).
FRONTEND_DIST = REPO_ROOT / "ElderApp" / "dist"
FRONTEND_SRC = REPO_ROOT / "ElderApp"
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if o.strip()
]
