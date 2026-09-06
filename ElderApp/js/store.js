// The client's state is now a cache of the last server response plus which
// screen is open. Views read `state.data`; they never compute visibility,
// because by the time a payload reaches them the server has already decided.
import { loadUi, saveUi } from './data.js';

export let state = {
  // identity, from GET /api/session
  person: null,
  elder: null,
  circle: [],
  role: null,
  isProxy: false,
  // which screen is open (the only genuinely client-side state)
  screen: loadUi()?.screen || null,
  // the payload for the current screen, keyed by screen name
  data: {},
  loading: false,
  error: null,
};

export function setSession(session) {
  state.person = session.person;
  state.elder = session.elder;
  state.circle = session.circle || [];
  state.role = session.person ? (session.person.role === 'elder' ? 'elder' : 'caregiver') : null;
  state.isProxy = Boolean(session.person && session.person.is_proxy);
}

export function clearSession() {
  state.person = null;
  state.role = null;
  state.isProxy = false;
  state.screen = null;
  state.data = {};
}

export function setData(key, payload) {
  state.data[key] = payload;
}

export function persist() {
  saveUi(state);
}
