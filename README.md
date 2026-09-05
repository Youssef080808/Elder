# CareCircle

Elder care coordination for MuslimHacks 2026 — a demo that helps families and caregivers coordinate safer, more dignified care for elderly Muslims while respecting privacy, independence, and personal preferences.

## What's new in this pass

- **State persists across reloads.** Everything (permissions, handoff notes, proxy status, activity log) is saved to `localStorage` and restored automatically. Refreshing the tab no longer resets the demo.
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

## Architecture

```
index.html          — shell, loads app.js as a module
app.js               — entry point: import render, call it once
js/
  data.js            — constants (categories, people, presets) + state factory + localStorage
  store.js           — the single mutable `state` object; resetState() / persist()
  helpers.js          — small pure/DOM utilities (avatar, toast, addLog, ...)
  views.js           — pure render functions: state in, HTML string out. No event binding.
  actions.js         — all event binding + state mutation. Calls render() after each change.
  render.js          — dispatches state.role/state.screen to the right view, wires up actions
style.css            — design tokens + component styles
```

Data flows one direction: `data.js → store.js → views.js`, and `actions.js` is the only place that writes to `store.js` and triggers a re-render. This keeps each file's job legible on its own — useful for the "is the architecture discernible" judging criterion.

A jsdom-based smoke test (`smoke-test.mjs`) exercises every screen and interaction end-to-end (login, all nav screens, permission toggles, presets, proxy flow, meds/handoff, persistence, logout, reset) — run it with `node smoke-test.mjs` after `npm install`.

## How to run locally

```
npm install
npm run dev
```

Or just open `index.html` directly in a browser — no build step is required for the demo itself (Vite is only used for the dev server and production bundling).

## How to deploy

The easiest path is **Vercel** or **Netlify**, both of which auto-detect this as a Vite project:

1. Push this folder to a GitHub repo (or update your existing `ElderApp` repo).
2. Go to vercel.com (or netlify.com) → "Add new project" → import the GitHub repo.
3. Framework preset: **Vite**. Build command: `npm run build`. Output directory: `dist`.
4. Deploy — you'll get a live URL in about a minute.

No environment variables, database, or backend are needed; it's a fully static site.
