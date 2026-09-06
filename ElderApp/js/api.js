// Every read and write goes through here. The browser holds no copy of
// Amira's record: it asks the server, and the server sends back only what the
// viewer is allowed to see. A category she has not shared is not in the
// response at all, so there is nothing here to filter and nothing in devtools
// to find.
const BASE = import.meta.env?.VITE_API_BASE ?? '';

async function request(path, options = {}) {
  const res = await fetch(`${BASE}/api${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  if (res.status === 401) return { unauthorized: true };
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) {
    const error = new Error(payload.detail || payload.error || 'Request failed');
    error.status = res.status;
    error.detail = payload.detail;
    throw error;
  }
  return payload;
}

const get = path => request(path);
const post = (path, body) => request(path, { method: 'POST', body });
const put = (path, body) => request(path, { method: 'PUT', body });
const del = path => request(path, { method: 'DELETE' });

export const api = {
  session: () => get('/session'),
  login: personId => post('/session/login', { person_id: personId }),
  logout: () => post('/session/logout'),

  overview: () => get('/elder/overview'),
  permissions: () => get('/elder/permissions'),
  togglePermission: (personId, category, granted) =>
    post('/elder/permissions/toggle', { person_id: personId, category, granted }),
  applyPreset: (personId, preset) =>
    post('/elder/permissions/preset', { person_id: personId, preset }),

  preferences: () => get('/elder/preferences'),
  savePreferences: prefs => put('/elder/preferences', prefs),

  activity: () => get('/elder/activity'),
  workload: () => get('/elder/workload'),
  preview: personId => get(`/elder/preview/${personId}`),

  appointProxy: personId => post('/elder/proxy', { person_id: personId }),
  revokeProxy: () => del('/elder/proxy'),

  shift: () => get('/shift'),
  markMedication: (shiftId, medicationId) =>
    post(`/shift/${shiftId}/medication`, { medication_id: medicationId }),
  writeHandoff: (shiftId, text) => post(`/shift/${shiftId}/handoff`, { text }),

  coverage: () => get('/coverage'),
  search: () => get('/search'),

  // Demo-only: rebuilds the seeded state on the server.
  reset: () => post('/demo/reset'),
};
