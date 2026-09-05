// Static data (categories, people, presets) and the state factory + persistence.
// This is the only file that knows about localStorage — everything else just
// reads/writes the `state` object exported from store.js.

export const categories = [
  { key: 'meds_schedule', label: 'Medication schedule', short: 'Names + times', icon: 'M' },
  { key: 'appointments', label: 'Appointments', short: 'Upcoming visits', icon: 'A' },
  { key: 'preferences', label: 'Preferences', short: 'Daily choices', icon: 'P' },
  { key: 'personal_care_log', label: 'Personal care log', short: 'Dignity-sensitive', icon: 'C' },
  { key: 'mood_notes', label: 'Mood notes', short: 'Private observations', icon: 'N' },
  { key: 'finances', label: 'Finances', short: 'Private records', icon: '$' }
];

// hours / shifts are this week's totals, used by the Workload view.
export const people = [
  { id: 'fatima', name: 'Fatima Rahman', role: 'Paid caregiver', initials: 'FR', tone: 'gold', hours: 32, shifts: 4 },
  { id: 'omar', name: 'Omar Hassan', role: 'Son · family', initials: 'OH', tone: '', hours: 6, shifts: 1 },
  { id: 'sara', name: 'Sara Hassan', role: 'Daughter · family', initials: 'SH', tone: '', hours: 3, shifts: 1 }
];

export const presets = {
  close_family: categories.map(c => c.key),
  paid_caregiver: ['meds_schedule', 'appointments', 'preferences', 'personal_care_log'],
  visiting_relative: ['appointments', 'preferences']
};

export const proxyId = 'omar';

const STORAGE_KEY = 'carecircle_state_v1';

export function freshState() {
  return {
    screen: 'overview', role: null,
    permissions: { fatima: [...presets.paid_caregiver], omar: [...presets.close_family], sara: [...presets.visiting_relative] },
    proxy: null,
    medsGiven: false, handoff: '',
    buffer: 20, caregiverGender: 'female',
    logs: [
      { who: 'Amira', text: 'updated Fatima’s access', time: 'Today, 8:42 AM', icon: 'P', proxy: false },
      { who: 'Amira', text: 'set bathing preference to female caregiver', time: 'Yesterday, 7:12 PM', icon: 'S', proxy: false },
      { who: 'Omar Hassan', text: 'viewed the care overview', time: 'Yesterday, 5:30 PM', icon: 'V', proxy: false }
    ]
  };
}

// Loads whatever was saved last session. Returns null (never throws) if
// storage is empty, unavailable (private browsing), or corrupted — callers
// fall back to freshState() in that case.
export function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === 'object' && parsed.permissions) return parsed;
    return null;
  } catch (e) {
    return null;
  }
}

export function saveState(state) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch (e) {
    // Storage can be unavailable (private mode, quota, disabled) — the demo
    // still works in-memory for the session, it just won't persist.
  }
}

export function clearState() {
  try { localStorage.removeItem(STORAGE_KEY); } catch (e) { /* ignore */ }
}
