import { state } from './store.js';
import { layout, loginHTML, elderOverview, permissions, workload, preferencesScreen, activity, shiftCard, coverage } from './views.js';
import { bindCommon, bindScreen, bindLogin } from './actions.js';

export function render() {
  const app = document.querySelector('#app');
  if (!state.role) {
    app.innerHTML = loginHTML();
    bindLogin();
    return;
  }

  let content = '';
  if (state.role === 'caregiver') {
    const active = state.screen === 'coverage' ? 'coverage' : 'shift';
    content = active === 'coverage' ? coverage() : shiftCard();
    app.innerHTML = layout(content, active);
  } else {
    if (state.screen === 'overview') content = elderOverview();
    else if (state.screen === 'permissions') content = permissions();
    else if (state.screen === 'workload') content = workload();
    else if (state.screen === 'preferences') content = preferencesScreen();
    else if (state.screen === 'activity') content = activity();
    else content = elderOverview();
    app.innerHTML = layout(content, state.screen);
  }
  bindCommon();
  bindScreen();
}
