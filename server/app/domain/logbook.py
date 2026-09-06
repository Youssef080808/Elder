"""Kinds of thing that can appear in the elder's activity log.

Separate from `app.models` so that route handlers, which are forbidden from
importing the ORM, can still name a log kind.
"""
from __future__ import annotations


class LogEntryKind(str):
    DISCLOSURE = "disclosure"  # what a person was shown
    CARE = "care"              # what a person did for the elder
    CONSENT = "consent"        # a change to who can see what
    PROXY = "proxy"            # appointing or revoking delegation


KIND_LABELS = {
    LogEntryKind.DISCLOSURE: "Shown",
    LogEntryKind.CARE: "Care",
    LogEntryKind.CONSENT: "Consent",
    LogEntryKind.PROXY: "Delegation",
}
