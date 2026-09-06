// UI constants and the tiny slice of state that is genuinely the browser's:
// which screen you are looking at. Everything about Amira — her permissions,
// her preferences, her care record — lives on the server and is fetched per
// screen, so closing the tab cannot leave a copy of it behind.
//
// This file used to hold the permission grid and the activity log in
// localStorage. That is exactly what made every permission cosmetic: the whole
// record reached the browser and the browser decided what to draw.

const UI_KEY = 'carecircle_ui_v2';

// Screens that exist per role, used by render.js to pick what to fetch.
export const ELDER_SCREENS = ['overview', 'permissions', 'workload', 'coverage', 'preferences', 'activity'];
export const CAREGIVER_SCREENS = ['shift', 'coverage'];

export function loadUi() {
  try {
    const raw = localStorage.getItem(UI_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === 'object') return { screen: parsed.screen || null };
    return null;
  } catch (e) {
    return null;
  }
}

export function saveUi(state) {
  try {
    localStorage.setItem(UI_KEY, JSON.stringify({ screen: state.screen }));
  } catch (e) {
    // Storage can be unavailable (private mode, quota, disabled). The demo
    // still works — it just won't remember which tab you were on.
  }
}

export function clearUi() {
  try { localStorage.removeItem(UI_KEY); } catch (e) { /* ignore */ }
}
