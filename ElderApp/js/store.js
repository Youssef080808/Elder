// The single source of truth for app state. Every other module imports
// `state` from here and mutates it directly (same pattern as the original
// app.js), so views always read the latest data with no plumbing required.
import { freshState, loadState, saveState } from './data.js';

export let state = loadState() || freshState();

// Restores demo defaults. Keeps the current role/screen by default so a
// mid-demo reset doesn't also kick the user back to the login screen.
export function resetState(keepRoleScreen = true) {
  const role = state.role;
  const screen = state.screen;
  state = freshState();
  if (keepRoleScreen) {
    state.role = role;
    state.screen = screen;
  }
  persist();
}

export function persist() {
  saveState(state);
}
