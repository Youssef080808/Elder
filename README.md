# CareCircle

Elder care coordination for MuslimHacks 2026 — a demo that helps families and caregivers coordinate safer, more dignified care for elderly Muslims while respecting privacy, independence, and personal preferences.

## What's new in this pass

- **A real backend.** FastAPI + SQLite now own every piece of Amira's record, and the browser holds none of it. See [Why the backend exists](#why-the-backend-exists) — this is the change that makes the privacy claim true rather than cosmetic.
- **State persists across reloads** — on the server, per person, in SQLite. Refreshing the tab no longer resets the demo, and closing it leaves no copy of her record behind.
- **Workload view.** A new screen shows care hours and shift counts per person this week, so "who is actually carrying the load" is visible at a glance — not just who has *access*.
- **"Why not WhatsApp" made explicit.** The login screen now states directly what a group chat can't do that CareCircle does.
- **Log out / Reset demo are always reachable** from the sidebar, in both views — useful for re-running the demo live in front of judges.
- **Modular code.** `app.js` is now a two-line entry point; everything else lives in `js/` split by responsibility (see Architecture below).

## Demo workflow

1. **Elder sets preferences** — caregiver gender for bathing (female) and a 20-minute prayer buffer before morning medication.
2. **Elder adds Fatima as caregiver** — the paid_caregiver preset pre-fills her permission column. Mood notes stay off.
3. **Fatima logs in for her 6:00 shift** — her shift card shows prayer at 5:40, meds after 6:00, breakfast constraints, and last night's handoff. Mood notes appear nowhere.
4. **Fatima marks meds as given** and writes one handoff line for the next caregiver.
5. **Elder opens the activity view** and sees what Fatima was shown and what she logged.
6. **Elder opens the workload view** and sees that Fatima is carrying 32 of the week's 41 care hours — a group chat wouldn't surface that.

## What's inside

- **Login** — choose Elder or Caregiver view (family logs in through Caregiver)
- **Permission grid** — six categories by three people, individual toggles, three presets
- **Workload** — hours and shifts per person this week, and how much is paid vs. family care
- **Preferences** — structured form with prayer buffer and caregiver gender wired to visible consequences
- **Shift card** — pushed to the caregiver, shows only what passes both permission and relevance filters
- **Coverage list** — seven days with gaps highlighted
- **Proxy** — appoint a family proxy who can manage others' access but not their own; finances excluded by default
- **Activity view** — the elder sees what was disclosed and what was logged

## Why the backend exists

The demo used to keep Amira's whole record — permissions, care notes, the activity
log — in `localStorage`, and each view decided what to draw from it. That is a
lovely front end and a broken privacy story: if the record is in the browser,
every permission is decorative. A judge with devtools open could read the mood
notes Amira chose not to share with Fatima, and the pitch's central claim would
not survive the question.

So the server now decides. `GET /api/shift` returns a payload assembled by one
function on the server, and **a category Amira has not shared is not a key in
that response** — not `null`, not `[]`, not a flag the client is trusted to
respect. There is nothing in the browser to find, and nothing for a client bug
to reveal.

```
Fatima's 6:00 shift            Amira's own screens
────────────────────           ───────────────────
prayer        ✓                everything
medications   ✓                + what Fatima was shown, built by
diet          ✓                  the same function through the
language      ✓                  same filters (no second code path)
personal_care ✓
withheld: appointments — "nothing scheduled during this shift"
(mood_notes and finances: no key, no trace, no way to tell they exist)
```

## Architecture

```
ElderApp/                       the front end, unchanged in shape
  index.html                    shell, loads app.js as a module
  app.js                        entry point: import render, call it once
  js/
    api.js                      every read and write. The only file that talks to the server.
    data.js                     UI constants + the one thing the browser may keep: which screen is open
    store.js                    a cache of the last server response, not a source of truth
    helpers.js                  small pure/DOM utilities (avatar, toast, clock, escaping)
    views.js                    pure render functions: payload in, HTML string out. No event binding,
                                and — the important part — no visibility decisions.
    actions.js                  event binding. Calls the API, re-renders from the response.
    render.js                   fetches what the current screen needs, then draws it
  style.css                     design tokens + component styles

server/                         FastAPI + SQLite
  app/api/routes_*.py           HTTP wiring only. No ORM, no visibility decisions.
  app/services/*.py             assemble payloads; every one asks the engine
  app/domain/*.py               permission engine, preferences, delegation rules.
                                Pure functions, no database.
  app/models.py                 SQLAlchemy tables
  app/seed.py                   deterministic demo data, rebuilt on boot
  tests/                        117 tests, 92% branch coverage
```

Data flows one direction on both sides: `models → domain → services → api` on the
server, and `api.js → store.js → views.js` in the browser, with `actions.js` the
only thing that writes. `server/tests/test_architecture.py` enforces it by parsing
the source — the build fails if a route handler reaches past a service into the
ORM, or if a client file starts hardcoding a permission set again.

### The permission engine

One function decides every disclosure:

```python
def visible_categories(person, ctx):
    return frozenset(
        c for c in CATEGORY_ORDER
        if has_permission(person, c) and is_relevant(c, ctx)
    )
```

Two filters, deliberately not collapsed into one, because they fail differently:

| | Filter A — Permission | Filter B — Relevance |
|---|---|---|
| Asks | Does this person's column grant this category? | Is this surface the moment for it? |
| Set by | Amira, or her proxy on her behalf | The shift and the screen |
| Fails how | Silently. No key, no trace, no hint the category exists. | Visibly. "Appointments — nothing scheduled during this shift." |

A caregiver blocked by Filter A must not be able to tell whether mood notes exist
at all. One blocked by Filter B has permission and is simply not being handed a
full calendar at six in the morning, so the UI says so.

### Delegation

At most one proxy at a time. Amira appoints; a proxy cannot appoint another. A
proxy manages everyone's column *except their own* — enforced server-side, so
POSTing straight past the UI returns a 403 with the rule that stopped it.
Delegation expires after 90 days. Every proxy action is logged as *"Omar Hassan,
acting as proxy, gave Fatima access to mood notes"* and is visible to every family
member, not only to Amira.

`finances` is excluded from every preset for a proxy, including the widest one. It
has to be granted on its own, one toggle, by Amira. Financial exploitation of
elders is overwhelmingly committed by family members; a one-click path that hands
the person administering consent the money as well would build the exact shape of
the problem.

## How to run locally

Two processes in development — FastAPI on `:8000`, Vite on `:5173` proxying `/api`
to it:

```
cd server
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload      # http://localhost:8000
```

```
cd ElderApp
npm install && npm run dev                   # http://localhost:5173
```

Or run **one** process: FastAPI serves `ElderApp/` (or `ElderApp/dist` if you have
built it) as static files, so `http://localhost:8000` gives you the whole demo with
no Node at all. The front end is native ES modules and needs no bundler.

### Tests

```
cd server
.venv/bin/python -m pytest                              # 117 tests, ~2s
.venv/bin/python -m coverage run -m pytest && .venv/bin/python -m coverage report
```

`test_payload_leakage.py` is the one to read first: it asserts, on the bytes of the
response, that a category Amira has not shared never reaches the browser.

The jsdom smoke test (`ElderApp/smoke-test.mjs`) predates the backend and still
targets the old `localStorage` state shape, so it needs updating before it will
pass again.

## How to deploy

One service, because the API serves the front end too.

**Railway / Render / Fly:**

1. Build the front end (optional — FastAPI will serve the source directly):
   `cd ElderApp && npm install && npm run build`
2. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT` from `server/`.
3. Health check: `/healthz`.

`RESEED_ON_BOOT=1` (the default) rebuilds the demo data on every boot: no volume to
mount, no migrations, and every demo starts from a known state. Set it to `0` with
a mounted volume to keep data between deploys.

**Cost of running:** one small container and a single SQLite file. No LLM, no paid
API, nothing in the request path that bills per use.
