// Everything that changes something calls the API and then re-renders from the
// server's response. Nothing in this file decides what is allowed: it asks, and
// a refusal comes back as a 403 with the rule that stopped it. Hiding a button
// is not a control, so the buttons that would break a rule are still wired —
// they just get told no.
import { api } from './api.js';
import { state, clearSession, persist } from './store.js';
import { clearUi } from './data.js';
import { showToast } from './helpers.js';
import { render } from './render.js';

async function run(fn, successMessage) {
  try {
    const result = await fn();
    if (successMessage) showToast(successMessage);
    await render();
    return result;
  } catch (err) {
    // 403s here are the delegation rules doing their job, and they explain
    // themselves. Show the server's sentence rather than inventing one.
    showToast(err.detail || err.message || 'That did not work');
    await render();
    return null;
  }
}

export function bindLogin() {
  document.querySelectorAll('[data-person]').forEach(el => el.addEventListener('click', async () => {
    const result = await api.login(el.dataset.person);
    state.screen = result.landing;
    persist();
    await render();
  }));
}

export function bindCommon() {
  document.querySelectorAll('[data-screen]').forEach(el => el.addEventListener('click', async () => {
    state.screen = el.dataset.screen;
    persist();
    await render();
  }));

  document.querySelectorAll('[data-action="switch"]').forEach(el => el.addEventListener('click', async () => {
    // The demo's fast path between the two sides of the story. Signing in as
    // someone else is a real sign-in: the server issues their session, and
    // their screens are built from their permissions, not from a client flag.
    const target = state.role === 'elder'
      ? (state.circle.find(p => p.role === 'caregiver') || state.circle[0])
      : state.elder;
    if (!target) return;
    const result = await api.login(target.id);
    state.screen = result.landing;
    persist();
    await render();
  }));

  document.querySelectorAll('[data-action="logout"]').forEach(el => el.addEventListener('click', async () => {
    await api.logout();
    clearSession();
    clearUi();
    await render();
  }));

  document.querySelectorAll('[data-action="reset"]').forEach(el => el.addEventListener('click', showReset));
  document.querySelectorAll('[data-action="search"]').forEach(el => el.addEventListener('click', async () => {
    const result = await api.search();
    showToast(result.message);
  }));
}

export function bindScreen() {
  document.querySelectorAll('[data-toggle]').forEach(el => el.addEventListener('click', () => {
    const [personId, category, granting] = el.dataset.toggle.split('|');
    run(() => api.togglePermission(personId, category, granting === '1'),
      `${category.replace(/_/g, ' ')} ${granting === '1' ? 'granted' : 'revoked'}`);
  }));

  document.querySelectorAll('[data-preset]').forEach(el => el.addEventListener('click', () => {
    const [personId, preset] = el.dataset.preset.split('|');
    run(() => api.applyPreset(personId, preset), 'Preset applied');
  }));

  document.querySelectorAll('[data-meds]').forEach(el => el.addEventListener('click', () => {
    const [shiftId, medicationId] = el.dataset.meds.split('|');
    if (!medicationId) return;
    run(() => api.markMedication(shiftId, medicationId), 'Medication marked as given');
  }));

  document.querySelectorAll('[data-handoff]').forEach(el =>
    el.addEventListener('click', () => showHandoff(el.dataset.handoff)));

  document.querySelectorAll('[data-action="proxy"]').forEach(el => el.addEventListener('click', showProxy));

  const form = document.querySelector('#preferences-form');
  if (form) form.addEventListener('submit', e => {
    e.preventDefault();
    const data = new FormData(form);
    const current = state.data.preferences || {};
    run(() => api.savePreferences({
      caregiver_gender: {
        bathing: data.get('bathing'),
        meals: data.get('meals'),
        transport: (current.caregiver_gender || {}).transport || 'any',
      },
      prayer_times: {
        ...(current.prayer_times || {}),
        method: data.get('method'),
        buffer_min: Number(data.get('buffer_min')),
        fajr: data.get('fajr'),
        dhuhr: data.get('dhuhr'),
      },
      diet: {
        ...(current.diet || {}),
        meat: data.get('meat'),
        substitutes: String(data.get('substitutes') || '').split(',').map(s => s.trim()).filter(Boolean),
      },
      language: { spoken: data.get('spoken'), written: data.get('written') },
      notes: data.get('notes'),
    }), 'Preferences saved — the shift card is updated');
  });
}

function modal(html) {
  document.body.insertAdjacentHTML('beforeend', `<div class="modal-backdrop" id="modal"><div class="modal">${html}</div></div>`);
  const close = () => { const m = document.querySelector('#modal'); if (m) m.remove(); };
  document.querySelector('[data-close]').onclick = close;
  return close;
}

function showHandoff(shiftId) {
  const card = (state.data.shift || {}).card || {};
  const existing = card.handoff_out ? card.handoff_out.text : '';
  const close = modal(`<p class="eyebrow">End of shift</p><h2>Leave one clear line.</h2><p>The next caregiver will see this on their shift card. Keep it practical and kind.</p><div class="field"><label>Handoff note</label><textarea id="handoff-input" placeholder="For the next caregiver…">${existing}</textarea></div><div class="modal-actions"><button class="btn" data-close>Cancel</button><button class="btn primary" data-save-handoff>Save handoff</button></div>`);
  document.querySelector('[data-save-handoff]').onclick = () => {
    const value = document.querySelector('#handoff-input').value.trim();
    if (!value) { showToast('Write one line before saving'); return; }
    close();
    run(() => api.writeHandoff(shiftId, value), 'Handoff shared with the next caregiver');
  };
}

function showProxy() {
  const grid = state.data.permissions || {};
  if (grid.proxy) {
    // Revoking is the elder's alone. A proxy pressing this gets a 403 with the
    // reason, which is the point: the rule lives on the server.
    const close = modal(`<p class="eyebrow">Shared stewardship</p><h2>${grid.proxy.name} is your proxy</h2><p>They can manage access for others on your behalf, but cannot change their own column and cannot be granted finances by any preset. ${grid.proxy_days_left} days remain.</p><div class="modal-actions"><button class="btn" data-close>Keep as is</button><button class="btn primary" data-revoke>End their proxy role</button></div>`);
    document.querySelector('[data-revoke]').onclick = () => { close(); run(() => api.revokeProxy(), 'Proxy role ended'); };
    return;
  }
  const family = (grid.columns || []).map(c => c.person).filter(p => p.role === 'family');
  const options = family.map(p => `<option value="${p.id}">${p.name} · ${p.role_label}</option>`).join('');
  const close = modal(`<p class="eyebrow">Shared stewardship</p><h2>Appoint a proxy</h2><p>A proxy can manage access for others on your behalf, but cannot change their own column, cannot appoint another proxy, and is never granted financial access by a preset. Every action is visible to the whole family.</p><div class="field"><label>Choose a family member</label><select id="proxy-select">${options}</select></div><div class="field" style="margin-top:14px"><label>Access ends</label><select disabled><option>In 90 days</option></select></div><div class="modal-actions"><button class="btn" data-close>Cancel</button><button class="btn primary" data-save-proxy>Appoint proxy</button></div>`);
  document.querySelector('[data-save-proxy]').onclick = () => {
    const id = document.querySelector('#proxy-select').value;
    close();
    run(() => api.appointProxy(id), 'Proxy appointed for 90 days');
  };
}

function showReset() {
  const close = modal(`<p class="eyebrow">Start fresh</p><h2>Reset the demo?</h2><p>This restores the original demo data on the server: Fatima as paid caregiver, Omar and Sara as family, and every permission back to its preset.</p><div class="modal-actions"><button class="btn" data-close>Cancel</button><button class="btn primary" data-save-reset>Reset</button></div>`);
  document.querySelector('[data-save-reset]').onclick = async () => {
    close();
    await run(() => api.reset(), 'Demo reset to its original state');
  };
}
