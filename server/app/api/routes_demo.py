"""Demo-only controls.

The reset button in the UI rebuilds the seeded state. It exists because a live
demo needs a reliable way back to a known starting point, and it is the honest
place for that: the browser cannot reset anything, because the browser owns
nothing.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import require_person

router = APIRouter(prefix="/api/demo", tags=["demo"])


@router.post("/reset")
def reset(person=Depends(require_person)):
    from app.seed import reseed

    reseed()
    return {"reset": True}
