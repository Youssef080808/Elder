// Everything that mutates `state` lives here. Each handler mutates state,
// persists it, then calls render() to redraw. views.js never does this —
// it only reads state and returns HTML.
import { presets, proxyId, categories, people } from './data.js';
import { state, resetState, persist } from './store.js';
import { showToast, addLog, proxyLocked } from './helpers.js';
import { render } from './render.js';

export function bindLogin() {
  document.querySelectorAll('[data-role]').forEach(el => el.addEventListener('click', () => {
    state.role = el.dataset.role;
    state.screen = el.dataset.role === 'elder' ? 'overview' : 'shift';
    persist();
    render();
  }));
}

export function bindCommon() {
  document.querySelectorAll('[data-screen]').forEach(el => el.addEventListener('click', () => {
    state.screen = el.dataset.screen;
    persist();
    render();
  }));
  document.querySelectorAll('[data-action="switch"]').forEach(el => el.addEventListener('click', () => {
    state.role = state.role === 'elder' ? 'caregiver' : 'elder';
    state.screen = state.role === 'elder' ? 'activity' : 'shift';
    persist();
    render();
  }));
  document.querySelectorAll('[data-action="logout"]').forEach(el => el.addEventListener('click', () => {
    state.role = null;
    state.screen = 'overview';
    persist();
    render();
  }));
  document.querySelectorAll('[data-action="reset"]').forEach(el => el.addEventListener('click', showReset));
}

export function bindScreen() {
  document.querySelectorAll('[data-toggle]').forEach(el => el.addEventListener('click', () => {
    const [personId, key] = el.dataset.toggle.split('|');
    if (state.role === 'caregiver') return;
    if (proxyLocked(state, personId)) { showToast('A proxy cannot change their own access'); return; }
    const list = state.permissions[personId];
    const granting = !list.includes(key);
    state.permissions[personId] = granting ? [...list, key] : list.filter(x => x !== key);
    const p = people.find(x => x.id === personId);
    const c = categories.find(x => x.key === key);
    const actor = state.proxy === proxyId ? 'Omar Hassan' : 'Amira';
    addLog(state, actor, `${granting ? 'gave' : 'removed'} ${c.label.toLowerCase()} access for ${p.name.split(' ')[0]}`, 'P', state.proxy === proxyId);
    showToast(`${c.label} ${granting ? 'granted' : 'revoked'} for ${p.name.split(' ')[0]}`);
    persist();
    render();
  }));

  document.querySelectorAll('[data-preset]').forEach(el => el.addEventListener('click', () => {
    state.permissions.fatima = [...presets[el.dataset.preset]];
    const actor = state.proxy === proxyId ? 'Omar Hassan' : 'Amira';
    addLog(state, actor, `applied ${el.dataset.preset.replace(/_/g, ' ')} preset to Fatima`, 'P', state.proxy === proxyId);
    showToast('Preset applied to Fatima');
    persist();
    render();
  }));

  document.querySelectorAll('[data-action="meds"]').forEach(el => el.addEventListener('click', () => {
    if (state.medsGiven) return;
    state.medsGiven = true;
    addLog(state, 'Fatima Rahman', 'marked morning medication as given', 'M');
    showToast('Medication marked as given');
    persist();
    render();
  }));

  document.querySelectorAll('[data-action="handoff"]').forEach(el => el.addEventListener('click', showHandoff));
  document.querySelectorAll('[data-action="proxy"]').forEach(el => el.addEventListener('click', showProxy));
  document.querySelectorAll('[data-action="search"]').forEach(el => el.addEventListener('click', () => showToast('Search is reserved for the next release. Your shift card is the source of truth for now.')));

  const form = document.querySelector('#preferences-form');
  if (form) form.addEventListener('submit', e => {
    e.preventDefault();
    const data = new FormData(form);
    state.buffer = Number(data.get('buffer'));
    state.caregiverGender = data.get('caregiverGender');
    addLog(state, 'Amira', 'updated daily preferences', 'S');
    showToast('Preferences saved — Fatima’s shift is updated');
    persist();
    setTimeout(render, 300);
  });
}

function showHandoff() {
  document.body.insertAdjacentHTML('beforeend', `<div class="modal-backdrop" id="modal"><div class="modal"><p class="eyebrow">End of shift</p><h2>Leave one clear line.</h2><p>The next caregiver will see this on their shift card. Keep it practical and kind.</p><div class="field"><label>Handoff note</label><textarea id="handoff-input" placeholder="For the next caregiver…">${state.handoff || ''}</textarea></div><div class="modal-actions"><button class="btn" data-close>Cancel</button><button class="btn primary" data-save-handoff>Save handoff</button></div></div></div>`);
  document.querySelector('[data-close]').onclick = () => document.querySelector('#modal').remove();
  document.querySelector('[data-save-handoff]').onclick = () => {
    const value = document.querySelector('#handoff-input').value.trim();
    if (!value) { showToast('Write one line before saving'); return; }
    state.handoff = value;
    addLog(state, 'Fatima Rahman', 'left a handoff note for the next caregiver', 'H');
    document.querySelector('#modal').remove();
    showToast('Handoff shared with the next caregiver');
    persist();
    render();
  };
}

function showProxy() {
  if (state.proxy) { showToast('Omar is already your proxy'); return; }
  document.body.insertAdjacentHTML('beforeend', `<div class="modal-backdrop" id="modal"><div class="modal"><p class="eyebrow">Shared stewardship</p><h2>Appoint a proxy</h2><p>A proxy can manage access for others on your behalf, but cannot change their own column or grant financial access by default. Every action is visible to the whole family.</p><div class="field"><label>Choose a family member</label><select id="proxy-select"><option>Omar Hassan</option><option>Sara Hassan</option></select></div><div class="field" style="margin-top:14px"><label>Access ends</label><select><option>In 90 days</option><option>In 30 days</option><option>Choose a date</option></select></div><div class="modal-actions"><button class="btn" data-close>Cancel</button><button class="btn primary" data-save-proxy>Appoint proxy</button></div></div></div>`);
  document.querySelector('[data-close]').onclick = () => document.querySelector('#modal').remove();
  document.querySelector('[data-save-proxy]').onclick = () => {
    state.proxy = proxyId;
    addLog(state, 'Amira', 'appointed Omar as proxy for 90 days', 'D');
    document.querySelector('#modal').remove();
    showToast('Omar is now your proxy for 90 days');
    persist();
    render();
  };
}

function showReset() {
  document.body.insertAdjacentHTML('beforeend', `<div class="modal-backdrop" id="modal"><div class="modal"><p class="eyebrow">Start fresh</p><h2>Reset the demo?</h2><p>This restores the original demo data: Fatima as paid caregiver, Omar and Sara as family, and all permissions back to their presets.</p><div class="modal-actions"><button class="btn" data-close>Cancel</button><button class="btn primary" data-save-reset>Reset</button></div></div></div>`);
  document.querySelector('[data-close]').onclick = () => document.querySelector('#modal').remove();
  document.querySelector('[data-save-reset]').onclick = () => {
    resetState(true);
    document.querySelector('#modal').remove();
    showToast('Demo reset to its original state');
    render();
  };
}
