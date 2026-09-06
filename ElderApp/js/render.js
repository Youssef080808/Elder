// Fetch what this screen needs, then draw it. Rendering is async now because
// the browser no longer holds the record — it asks the server every time, which
// is what makes a revoked permission take effect on the next screen rather
// than the next sign-in.
import { api } from './api.js';
import { state, setSession, setData, persist } from './store.js';
import {
  layout, loginHTML, elderOverview, permissions, workload,
  preferencesScreen, activity, shiftCard, coverage, errorPanel,
} from './views.js';
import { bindCommon, bindScreen, bindLogin } from './actions.js';

const LOADERS = {
  overview: () => api.overview(),
  permissions: () => api.permissions(),
  workload: () => api.workload(),
  coverage: () => api.coverage(),
  preferences: () => api.preferences(),
  activity: async () => {
    const log = await api.activity();
    const caregiver = (log.circle || []).find(p => p.role === 'caregiver');
    const preview = caregiver ? await api.preview(caregiver.id) : null;
    return { ...log, preview };
  },
  shift: () => api.shift(),
};

function defaultScreen(role) {
  return role === 'elder' ? 'overview' : 'shift';
}

function screenFor(role, screen) {
  const allowed = role === 'elder'
    ? ['overview', 'permissions', 'workload', 'coverage', 'preferences', 'activity']
    : ['shift', 'coverage'];
  return allowed.includes(screen) ? screen : defaultScreen(role);
}

export async function render() {
  const app = document.querySelector('#app');

  const session = await api.session();
  setSession(session);

  if (!state.person) {
    app.innerHTML = loginHTML();
    bindLogin();
    return;
  }

  const active = screenFor(state.role, state.screen);
  state.screen = active;
  persist();

  let payload;
  try {
    payload = await LOADERS[active]();
  } catch (err) {
    app.innerHTML = layout(errorPanel(err), active);
    bindCommon();
    return;
  }
  setData(active, payload);

  let content;
  if (active === 'overview') content = elderOverview(payload);
  else if (active === 'permissions') content = permissions(payload);
  else if (active === 'workload') content = workload(payload);
  else if (active === 'coverage') content = coverage(payload);
  else if (active === 'preferences') content = preferencesScreen(payload);
  else if (active === 'activity') content = activity(payload);
  else content = shiftCard(payload);

  app.innerHTML = layout(content, active);
  bindCommon();
  bindScreen();
}
