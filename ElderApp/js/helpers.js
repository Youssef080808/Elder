import { proxyId } from './data.js';

export function avatar(person, extra = '') {
  return `<span class="avatar ${extra || person.tone || ''}">${person.initials}</span>`;
}

export function medicationDisplay(buffer) {
  const minutes = 6 * 60 - buffer;
  return `After ${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
}

export function nowLabel() {
  const d = new Date();
  let h = d.getHours();
  const m = d.getMinutes();
  const ampm = h >= 12 ? 'PM' : 'AM';
  h = h % 12 || 12;
  return `Today, ${h}:${String(m).padStart(2, '0')} ${ampm}`;
}

export function showToast(message) {
  const toast = document.querySelector('#toast');
  if (!toast) return;
  toast.textContent = message;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 2600);
}

export function addLog(state, who, text, icon, proxy = false) {
  state.logs.unshift({ who, text, time: nowLabel(), icon, proxy });
}

export function proxyLocked(state, personId) {
  return state.proxy === proxyId && personId === proxyId;
}
