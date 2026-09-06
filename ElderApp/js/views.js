// Pure render functions: each takes the payload the server sent for its screen
// and returns an HTML string. Nothing here binds events, mutates state, or
// decides visibility — that last part is the change that matters. These
// functions can only draw what is in the payload, and a category Amira has not
// shared is not in the payload at all.
import { state } from './store.js';
import { avatar, clock, timeAgoLabel, escapeHtml as esc } from './helpers.js';

export function layout(content, active) {
  const person = state.person || {};
  const elder = state.elder || { name: 'Amira Hassan' };
  const isElder = state.role === 'elder';
  const switcher = isElder
    ? `<button class="btn" data-action="switch" title="Switch to caregiver view">Caregiver view →</button>`
    : `<button class="btn" data-action="switch" title="Switch to elder view">← Elder view</button>`;
  const crumbTail = active === 'overview' || active === 'shift'
    ? 'Today'
    : active[0].toUpperCase() + active.slice(1);

  return `<div class="shell"><aside class="sidebar"><div class="brand"><div class="brand-mark"></div><div><strong>CareCircle</strong><span>care, held with dignity</span></div></div><div class="profile-switch"><div class="avatar gold">${esc(person.initials)}</div><div><small>Signed in as</small><strong>${esc(person.name)}</strong></div><span class="chev">⌄</span></div>${state.isProxy ? `<div class="proxy-banner" style="margin:0 0 12px"><span class="proxy-badge">D</span><div><strong>Acting as proxy</strong><p>Every action you take here is written to ${esc(elder.name.split(' ')[0])}'s activity feed and visible to the whole family.</p></div></div>` : ''}<div class="nav-label">${isElder ? 'Your care space' : 'Your shift space'}</div><nav class="nav">${navItems(active)}</nav><div class="sidebar-bottom">${isElder ? '<b>Private by design</b>Every choice is yours. Access is separate for each person and each kind of information.' : `<b>Limited by ${esc(elder.name.split(' ')[0])}</b>You see only what is relevant to this shift and what ${esc(elder.name.split(' ')[0])} has chosen to share.`}<button class="btn ghost" data-action="reset" style="width:100%;margin-top:12px;font-size:10px">Reset demo</button></div></aside><main class="main"><header class="topbar"><div class="crumb">${isElder ? 'Care space' : `${esc(person.first_name)}’s shift`} <span> / </span> <b>${esc(crumbTail)}</b></div><div class="top-actions">${switcher}<button class="btn" data-action="logout" title="Return to login">Log out</button><span class="privacy-chip"><i class="dot"></i> ${isElder ? 'Consent is up to date' : 'Limited view'}</span><span class="top-avatar">${esc(person.initials)}</span></div></header>${content}</main></div>`;
}

export function navItems(active) {
  const item = (screen, icon, label) =>
    `<button class="${active === screen ? 'active' : ''}" data-screen="${screen}"><span class="nav-icon">${icon}</span>${label}</button>`;
  if (state.role === 'elder') {
    return item('overview', '⌂', 'Overview') + item('permissions', '◈', 'Permissions')
      + item('workload', '▤', 'Workload') + item('coverage', '▦', 'Schedule')
      + item('preferences', '◌', 'Preferences') + item('activity', '↗', 'Activity');
  }
  return item('shift', '◷', 'My shift') + item('coverage', '▦', 'Coverage')
    + `<button data-action="search"><span class="nav-icon">⌕</span>Search</button>`;
}

export function errorPanel(err) {
  return `<div class="content"><p class="eyebrow">Not allowed</p><h1 class="page-title">${esc(err.detail || err.message)}</h1><p class="page-subtitle">This rule is enforced on the server, not by hiding a button. Nothing was changed.</p></div>`;
}

export function loginHTML() {
  return `<div class="login-page"><section class="login-visual"><div class="brand"><div class="brand-mark"></div><div><strong>CareCircle</strong><span>care, held with dignity</span></div></div><div class="login-copy"><p class="eyebrow">Elder care, together</p><h1>A calmer way to care for the people who raised us.</h1><p>Coordinate the small details that make a day feel safe, familiar, and dignified — without giving away more than someone agreed to share.</p></div><div class="quote">“Care is not only what we do. It is how we let someone remain themselves.”</div><div class="compare-strip"><div class="compare-row"><span class="compare-label whatsapp">Family group chat</span><span class="compare-text">Buried in messages. No single answer for who agreed to what, and no view of who is actually carrying the week.</span></div><div class="compare-row"><span class="compare-label care">CareCircle</span><span class="compare-text">One current answer for consent, workload, and handoffs — visible to exactly the people it should be, and no one else.</span></div></div></section><section class="login-form"><div class="login-box"><p class="eyebrow">Welcome back</p><h2>Choose your view</h2><p>This is a private demo space. Select the view you would like to explore.</p><div class="role-card" data-person="${esc((state.elder || {}).id || 'amira')}"><div class="role-icon">◉</div><div class="info"><strong>Elder / family view</strong><span>Manage care, preferences, and consent</span></div><span class="arrow">→</span></div>${(state.circle || []).map(p => `<div class="role-card" data-person="${esc(p.id)}"><div class="role-icon">${p.role === 'caregiver' ? '✦' : '◈'}</div><div class="info"><strong>${esc(p.name)}</strong><span>${esc(p.role_label)}${p.is_proxy ? ' · proxy' : ''}</span></div><span class="arrow">→</span></div>`).join('')}<p class="login-note">No medical advice is provided here. Medication times are entered by a human and shown exactly as scheduled.</p></div></section></div>`;
}

// ---------------------------------------------------------------- elder

export function elderOverview(data) {
  const first = (data.elder.first_name) || 'Amira';
  const card = data.primary_card;
  const caregiver = data.primary_caregiver;
  const morning = card ? (card.medications || [])[0] : null;
  const fajr = card && card.prayer ? (card.prayer.times.find(t => t.name === 'Fajr') || {}).at : null;

  const stats = `<div class="stat-row" style="margin-top:28px"><div class="stat"><span class="number">${data.stats.circle_size}</span><span class="label">People in your care circle</span><span class="trend">All access is intentional</span></div><div class="stat"><span class="number">${data.stats.covered_shifts}</span><span class="label">Shifts covered this week</span><span class="trend">${data.stats.open_days ? `${data.stats.open_days} day${data.stats.open_days === 1 ? '' : 's'} still need someone` : 'Every day is covered'}</span></div><div class="stat"><span class="number">${data.stats.categories}</span><span class="label">Categories you control</span><span class="trend">Nothing shared globally</span></div></div>`;

  const proxyBanner = data.proxy
    ? `<div class="proxy-banner" style="margin-top:22px"><span class="proxy-badge">D</span><div><strong>${esc(data.proxy.first_name)} is your proxy</strong><p>He can manage access for others on your behalf, but cannot change his own column. Finances are excluded by default, and every action appears in your activity feed. ${data.proxy_days_left} days left.</p></div></div>`
    : '';

  const shiftCardPanel = card
    ? `<div class="card pad"><div class="surface-header"><div><h3>${esc(caregiver.first_name)}’s ${esc((card.shift.label || 'shift').toLowerCase())}</h3><p>Today · <span class="nowrap">${clock(card.shift.start)}</span> –<br><span class="nowrap">${clock(card.shift.end)}</span></p></div><span class="status">${morning && morning.given ? 'Meds given' : 'Ready'}</span></div>${fajr ? `<div class="line-item"><div class="line-icon">P</div><div class="line-main"><strong>Prayer time</strong><span>Fajr · morning buffer is respected</span></div><span class="time-pill adjusted">${clock(fajr)}</span></div>` : ''}${morning ? `<div class="line-item"><div class="line-icon">M</div><div class="line-main"><strong>Morning medication</strong><span>${morning.shifted ? `Shown after your ${card.prayer.buffer_min}-minute prayer buffer` : 'As entered by a person'}</span></div><span class="time-pill ${morning.shifted ? 'adjusted' : ''}">${clock(morning.display_time)}</span></div>` : ''}${(card.diet || []).length ? `<div class="line-item"><div class="line-icon">B</div><div class="line-main"><strong>Breakfast</strong><span>${esc(card.diet.join(' · '))}</span></div></div>` : ''}${card.handoff_out ? `<div class="handoff"><div class="mini-label">Handoff from ${esc(caregiver.first_name)}</div><p>“${esc(card.handoff_out.text)}”</p></div>` : `<div class="note" style="margin-top:17px">This is the same information ${esc(caregiver.first_name)} receives — built by the same code, through the same filters.</div>`}</div>`
    : `<div class="card pad"><h3>No shift running</h3><p style="font-size:11px;color:var(--muted)">Nobody is on a shift right now.</p></div>`;

  const peopleList = `<div class="card pad side-card"><h3>People &amp; access</h3><div class="person-list">${data.people.map(row => `<div class="person-item">${avatar(row.person)}<div class="info"><strong>${esc(row.person.first_name)}</strong><span>${esc(row.person.role_label)} · ${row.granted_count} of ${row.total} categories</span></div><span class="status ${row.person.role === 'caregiver' ? 'invited' : ''}">${row.person.role === 'caregiver' ? 'Caregiver' : 'Family'}</span></div>`).join('')}</div><button class="btn ghost" style="width:100%;margin-top:14px" data-screen="permissions">Open permission grid →</button></div>`;

  return `<div class="content"><p class="eyebrow">${esc(card ? card.shift.date_label : 'Today')}</p><h1 class="page-title">Good morning, ${esc(first)}.</h1><p class="page-subtitle">Your care space is calm and up to date. Here is what is happening today.</p>${stats}${proxyBanner}<div class="section-head"><div><h2>Today at a glance</h2><p>The next person arriving sees only what helps them care well.</p></div><button class="btn primary" data-screen="permissions">Review access</button></div><div class="grid two">${shiftCardPanel}${peopleList}</div></div>`;
}

export function permissions(data) {
  const header = data.columns.map(col => `<th><div class="person-head">${avatar(col.person)}<span>${esc(col.person.first_name)}</span>${col.person.is_proxy ? '<small style="display:block;font-size:9px;color:#9a6e35;margin-top:3px">proxy</small>' : ''}</div></th>`).join('');

  const rows = data.categories.map((c, rowIndex) => {
    const cells = data.columns.map(col => {
      const cell = col.cells[rowIndex];
      return `<td><button class="toggle ${cell.granted ? 'on' : ''}" data-toggle="${esc(col.person.id)}|${esc(cell.category)}|${cell.granted ? '0' : '1'}" ${cell.locked ? 'disabled' : ''} title="${esc(cell.lock_reason)}" aria-label="${esc(c.label)} for ${esc(col.person.name)}"></button>${cell.locked ? '<div style="font-size:9px;color:#9a6e35;margin-top:5px">locked</div>' : ''}</td>`;
    }).join('');
    return `<tr><td><div class="category"><span class="category-icon">${esc(c.icon)}</span><div>${esc(c.label)}<small>${esc(c.short)}</small></div></div></td>${cells}</tr>`;
  }).join('');

  const caregiver = (data.columns.find(col => col.person.role === 'caregiver') || {}).person;
  const presetRow = caregiver
    ? `<div class="preset-row"><span style="font-size:11px;color:var(--muted);padding:9px 2px">Apply preset to ${esc(caregiver.first_name)}:</span>${data.presets.map(p => `<button class="btn" data-preset="${esc(caregiver.id)}|${esc(p.key)}" title="${esc(p.blurb)}">${esc(p.label)}</button>`).join('')}</div>`
    : '';

  return `<div class="content"><p class="eyebrow">Consent, made visible</p><h1 class="page-title">Who can see what?</h1><p class="page-subtitle">Each person has their own column. Change one person’s access without changing anyone else’s.</p><div class="section-head"><div><h2>Permission grid</h2><p>The current answer, not a history · changes take effect on the next screen</p></div><div style="display:flex;gap:8px"><button class="btn" data-action="reset">Reset demo</button><button class="btn gold" data-action="proxy">${data.proxy ? 'Proxy active' : 'Set up a proxy'}</button></div></div><div class="card table-wrap"><div class="table-title"><div><h3>${esc((state.elder || {}).name)}’s care information</h3><span>${data.categories.length} categories · no global sharing</span></div><span class="privacy-chip"><i class="dot"></i> Elder-controlled</span></div><table class="permission-table"><thead><tr><th>Information</th>${header}</tr></thead><tbody>${rows}</tbody></table><div style="padding:0 18px 20px">${presetRow}</div></div><div class="grid two" style="margin-top:17px"><div class="note"><b>Permission and relevance are separate.</b><br>Even with permission, a caregiver only sees what is relevant to the shift in front of them. ${caregiver ? esc(caregiver.first_name) : 'A caregiver'} sees the morning handoff, not a full care history.</div><div class="card pad"><h3 style="font-size:13px;margin:0 0 9px">The promise</h3><p style="font-size:11px;color:var(--muted);line-height:1.6;margin:0">Your consent is not buried in past activity. This grid is the current answer, at all times — and it is the server that enforces it.</p></div></div></div>`;
}

export function workload(data) {
  const rows = data.people;
  const maxHours = Math.max(1, ...rows.map(p => p.hours));
  const totalHours = rows.reduce((sum, p) => sum + p.hours, 0) || 1;
  const paid = rows.find(p => p.role_label && p.role_label.toLowerCase().includes('paid'));
  const paidPct = paid ? Math.round((paid.hours / totalHours) * 100) : 0;

  const bars = rows.map(p => {
    const pct = Math.round((p.hours / maxHours) * 100);
    return `<div class="workload-row"><div class="workload-person">${avatar(p)}<div><strong>${esc(p.name)}</strong><span>${esc(p.role_label)}</span></div></div><div class="workload-bar-wrap"><div class="workload-bar"><div class="workload-fill" style="width:${pct}%"></div></div></div><div class="workload-figures"><strong>${p.hours}h</strong><span>${p.shifts} shift${p.shifts === 1 ? '' : 's'} this week</span></div></div>`;
  }).join('');

  return `<div class="content"><p class="eyebrow">Shared load, made visible</p><h1 class="page-title">Workload</h1><p class="page-subtitle">A group chat can’t show you this at a glance. See how care hours are actually divided before resentment builds quietly.</p><div class="stat-row" style="margin-top:28px"><div class="stat"><span class="number">${totalHours}h</span><span class="label">Total care hours this week</span><span class="trend">Across ${rows.length} people</span></div><div class="stat"><span class="number">${paidPct}%</span><span class="label">of care hours are done by paid help</span><span class="trend">${paid ? `${esc(paid.name)} · ${paid.hours} of ${totalHours}h` : 'No paid caregiver on the rota'}</span></div><div class="stat"><span class="number">${rows.reduce((s, p) => s + p.shifts, 0)}</span><span class="label">Shifts on the rota</span><span class="trend">This coming week</span></div></div><div class="card pad" style="margin-top:22px"><h3 style="font-size:14px;margin:0 0 6px">Hours by person</h3><p style="font-size:11px;color:var(--muted);margin:0 0 8px">This week, by who is on the shift</p>${bars}</div><div class="note" style="margin-top:17px"><b>Why this matters:</b> a family chat shows messages, not balance. When one person quietly carries most of the week, CareCircle surfaces it before it becomes burnout — or a fight.</div></div>`;
}

export function preferencesScreen(prefs) {
  const gender = key => ['female', 'male', 'any'].map(v =>
    `<option value="${v}" ${prefs.caregiver_gender[key] === v ? 'selected' : ''}>${v === 'any' ? 'Any caregiver' : v[0].toUpperCase() + v.slice(1) + ' caregiver'}</option>`).join('');

  const meats = [['zabiha_only', 'Zabiha only'], ['halal_certified', 'Halal certified'], ['any', 'Any'], ['other', 'Other']]
    .map(([v, label]) => `<option value="${v}" ${prefs.diet.meat === v ? 'selected' : ''}>${label}</option>`).join('');

  const methods = ['ISNA', 'MWL', 'Umm al-Qura', 'Egyptian', 'Karachi']
    .map(m => `<option value="${m}" ${prefs.prayer_times.method === m ? 'selected' : ''}>${m}</option>`).join('');

  const buffers = [0, 10, 20, 30, 45]
    .map(n => `<option value="${n}" ${prefs.prayer_times.buffer_min === n ? 'selected' : ''}>${n} minutes</option>`).join('');

  return `<div class="content"><p class="eyebrow">Your daily choices</p><h1 class="page-title">Preferences</h1><p class="page-subtitle">Small details make care feel like yours. These choices are shown only to people you have allowed. There is no single “Muslim-friendly” switch here, because there is no such person.</p><form class="card pad" style="margin-top:29px" id="preferences-form"><div class="form-section"><h3>Caregiver comfort</h3><div class="form-grid"><div class="field"><label>Bathing assistance</label><select name="bathing">${gender('bathing')}</select><small style="display:block;color:var(--muted);font-size:10px;margin-top:6px">This flags a mismatch on the schedule when a shift includes bathing.</small></div><div class="field"><label>Meal assistance</label><select name="meals">${gender('meals')}</select></div></div></div><div class="form-section"><h3>Prayer times</h3><div class="form-grid"><div class="field"><label>Prayer time method</label><select name="method">${methods}</select></div><div class="field"><label>Buffer before medication</label><select name="buffer_min">${buffers}</select><small style="display:block;color:var(--muted);font-size:10px;margin-top:6px">Moves when a dose is offered. It never changes the dose.</small></div></div><div class="form-grid" style="margin-top:18px"><div class="field"><label>Fajr</label><input name="fajr" value="${esc(prefs.prayer_times.fajr)}"></div><div class="field"><label>Dhuhr</label><input name="dhuhr" value="${esc(prefs.prayer_times.dhuhr)}"></div></div></div><div class="form-section"><h3>Food &amp; language</h3><div class="form-grid"><div class="field"><label>Meat</label><select name="meat">${meats}</select></div><div class="field"><label>Substitutes</label><input name="substitutes" value="${esc((prefs.diet.substitutes || []).join(', '))}"></div><div class="field"><label>Spoken language</label><input name="spoken" value="${esc(prefs.language.spoken)}"></div><div class="field"><label>Written language</label><input name="written" value="${esc(prefs.language.written)}"></div></div></div><div class="form-section"><h3>Notes for a good day</h3><div class="field"><label>Visible note</label><textarea name="notes">${esc(prefs.notes)}</textarea><small style="display:block;color:var(--muted);font-size:10px;margin-top:6px">Free text. People read it; no code acts on it.</small></div></div><div style="display:flex;justify-content:flex-end"><button class="btn primary" type="submit">Save preferences</button></div></form></div>`;
}

export function activity(data) {
  const preview = data.preview;
  const card = preview && preview.card;
  const who = preview && preview.person;

  const shown = card
    ? `${card.prayer ? `<div class="reveal"><div class="mini-label">Preferences</div><p>Fajr at ${clock((card.prayer.times.find(t => t.name === 'Fajr') || {}).at)}, ${card.prayer.buffer_min}-minute buffer before medication. ${esc((card.diet || []).join('. '))} ${esc((card.language || []).join('. '))}</p></div>` : ''}${card.medications ? `<div class="reveal"><div class="mini-label">Medication schedule</div><p>${card.medications.map(m => `${esc(m.name)} at ${clock(m.display_time)}${m.shifted ? ' (moved by your prayer buffer)' : ''}`).join('; ')}. Entered by a person; CareCircle does not advise on medication.</p></div>` : ''}${card.handoff_in ? `<div class="reveal"><div class="mini-label">Handoff note</div><p>“${esc(card.handoff_in.text)}”</p></div>` : ''}${(card.medications || []).some(m => m.given) ? `<div class="reveal"><div class="mini-label">Care log</div><p>${card.medications.filter(m => m.given).map(m => `${esc(m.name)} marked given by ${esc(m.given_by)}`).join('; ')}.</p></div>` : ''}<div class="note" style="margin-top:15px"><b>What was withheld.</b> ${esc(who.first_name)} was shown ${card.visible.length} of 6 categories. ${card.withheld.length ? `${card.withheld.map(w => esc(w.label)).join(', ')} — permitted, but not part of this shift. ` : ''}Anything you have not shared with ${esc(who.first_name)} is not on her screen and is not in the data her browser received.</div>`
    : '<p style="font-size:11px;color:var(--muted)">No caregiver is on a shift right now.</p>';

  const logs = data.rows.map(l => `<div class="log"><div class="log-bullet">${esc(l.icon)}</div><div class="log-body"><strong>${esc(l.who)}${l.proxy ? ' · acting as proxy' : ''}</strong><p>${esc(l.text)}</p>${l.detail ? `<p style="color:var(--muted);font-size:10px;margin-top:3px">${esc(l.detail)}</p>` : ''}${l.categories && l.categories.length ? `<p style="color:var(--muted);font-size:10px;margin-top:3px">${l.categories.map(c => esc(c.replace(/_/g, ' '))).join(' · ')}</p>` : ''}</div><span class="log-time">${esc(timeAgoLabel(l.time))}</span></div>`).join('');

  return `<div class="content"><p class="eyebrow">Your window into care</p><h1 class="page-title">Activity</h1><p class="page-subtitle">See what was shared about you, and what your care circle recorded. Most care software never tells the person being cared for this part.</p><div class="grid two" style="margin-top:29px"><div class="card pad"><div class="surface-header"><div><h3>What ${who ? esc(who.first_name) : 'your caregiver'} is being shown</h3><p>The same payload her app receives — not a summary of it</p></div>${card ? `<span class="status">${clock(card.shift.start)} shift</span>` : ''}</div>${shown}</div><div class="card pad"><div class="surface-header"><div><h3>Recent activity</h3><p>A transparent record for your family</p></div><span class="privacy-chip">No exports</span></div><div class="log-list">${logs}</div></div></div></div>`;
}

// ------------------------------------------------------------ caregiver

export function shiftCard(data) {
  const card = data.card;
  if (!card) {
    return `<div class="content"><p class="eyebrow">Nothing scheduled</p><h1 class="page-title">You have no upcoming shifts.</h1><p class="page-subtitle">When you are put on a shift it appears here, without you having to look for it.</p></div>`;
  }

  // Each section below exists only because its key is in the payload, and its
  // key is in the payload only because the category passed both filters on the
  // server. There is no `if (permitted)` in this file, because there is nothing
  // here to hide.
  const anyGiven = (card.medications || []).some(m => m.given);

  const prayer = card.prayer
    ? `<div class="line-item"><div class="line-icon">P</div><div class="line-main"><strong>Prayer</strong><span>Fajr · prayer time before the morning routine</span></div><span class="time-pill">${clock((card.prayer.times.find(t => t.name === 'Fajr') || {}).at)}</span></div>`
    : '';

  const meds = (card.medications || []).map(m => `<div class="line-item"><div class="line-icon">M</div><div class="line-main"><strong>${esc(m.name)} · ${esc(m.dose_text)}</strong><span>${m.shifted ? esc(m.shift_reason) : esc(m.instructions)}</span><span style="display:block;font-size:9px;opacity:.65;margin-top:2px">${esc(m.entered_by)}</span>${m.given ? `<span style="display:block;font-size:10px;color:var(--muted);margin-top:3px">Given by ${esc(m.given_by)} at ${esc((m.given_at || '').slice(11))}</span>` : ''}</div>${m.given ? `<span class="time-pill">${clock(m.display_time)}</span>` : `<span class="time-pill ${m.shifted ? 'adjusted' : ''}">${clock(m.display_time)}</span>`}</div>`).join('');

  const diet = (card.diet || []).length
    ? `<div class="line-item"><div class="line-icon">B</div><div class="line-main"><strong>Breakfast constraints</strong><span>${esc(card.diet.join(' · '))}</span></div></div>` : '';

  const language = (card.language || []).length
    ? `<div class="line-item"><div class="line-icon">L</div><div class="line-main"><strong>Language</strong><span>${esc(card.language.join(' · '))}</span></div></div>` : '';

  const appointments = (card.appointments || []).map(a => `<div class="line-item"><div class="line-icon">A</div><div class="line-main"><strong>${esc(a.title)}</strong><span>${esc(a.location)}${a.escort ? ` · ${esc(a.escort)}` : ''}</span></div><span class="time-pill">${clock(a.time)}</span></div>`).join('');

  const handoff = card.handoff_out
    ? `<div class="handoff"><div class="mini-label">Your latest handoff</div><p>“${esc(card.handoff_out.text)}”</p></div>`
    : card.handoff_in
      ? `<div class="handoff"><div class="mini-label">Last night’s handoff · ${esc(card.handoff_in.author)}</div><p>“${esc(card.handoff_in.text)}”</p></div>`
      : '';

  const firstUngiven = (card.medications || []).find(m => !m.given);
  const actions = `<div class="action-area">${card.medications ? `<button class="btn ${firstUngiven ? '' : 'primary'}" data-meds="${esc(card.shift.id)}|${esc(firstUngiven ? firstUngiven.id : '')}" ${firstUngiven ? '' : 'disabled'}>${firstUngiven ? `Mark ${esc(firstUngiven.name)} as given` : 'Medication recorded'}</button>` : ''}${card.handoff_in !== undefined ? `<button class="btn" data-handoff="${esc(card.shift.id)}">${card.handoff_out ? 'Update handoff' : 'Write handoff'}</button>` : ''}</div>`;

  // Named, without content: these passed the elder's permission check and are
  // simply not part of this shift. Categories she blocked are not listed here
  // or anywhere else — there is no way to tell from this screen that they exist.
  const withheld = (card.withheld || []).length
    ? `<div class="note" style="margin-top:15px"><b>Not on this shift:</b> ${card.withheld.map(w => `${esc(w.label)} — ${esc(w.reason)}`).join(' ')} <br><span style="opacity:.75">Anything ${esc(card.elder.first_name)} has not shared with you is not listed here, or anywhere else.</span></div>`
    : '';

  const genderWarning = card.gender_warning
    ? `<div class="note" style="margin-top:15px;border-color:#c98a2e"><b>Check before bathing.</b> ${esc(card.gender_warning)}</div>` : '';

  const carePrefs = (card.care_preferences || []).map(line => `<div class="reveal"><div class="mini-label">${esc(line.split(':')[0])}</div><p>${esc(line.split(':').slice(1).join(':').trim())}</p></div>`).join('');

  const personalCare = (card.personal_care || []).map(n => `<div class="reveal"><div class="mini-label">${esc(n.day)} · ${esc(n.author)}</div><p>${esc(n.text)}</p></div>`).join('');

  const mood = (card.mood_notes || []).map(n => `<div class="reveal"><div class="mini-label">Mood · ${esc(n.day)} · ${esc(n.author)}</div><p>${esc(n.text)}</p></div>`).join('');

  return `<div class="content"><div class="shift-banner"><div><p class="eyebrow">${esc(card.shift.date_label)} · ${esc(card.shift.label)}</p><h2><span class="fraktur">Good morning,</span><br><span class="serif-name">${esc(card.caregiver.first_name)}</span>.</h2><p>Here is what matters for ${esc(card.elder.first_name)}’s care right now. You did not have to know what to ask for.</p></div><div class="shift-time"><strong>${clock(card.shift.start).split(' ')[0]}<em class="mer">${clock(card.shift.start).split(' ')[1].toLowerCase()}</em></strong><span>until ${clock(card.shift.end)}</span><div class="shift-status"><i class="dot"></i> ${anyGiven ? 'Meds recorded' : 'Shift in progress'}</div></div></div><div class="care-grid"><div><div class="card surface"><div class="surface-header"><div><h3>${esc(card.elder.first_name)}’s morning rhythm</h3><p>Only the information relevant to this shift</p></div><span class="status">Permissioned</span></div>${prayer}${meds}${diet}${language}${appointments}${handoff}${actions}</div>${genderWarning}${withheld}</div><div>${carePrefs ? `<div class="card pad"><div class="surface-header"><div><h3>Care preferences</h3><p>What helps ${esc(card.elder.first_name)} feel at home</p></div></div>${carePrefs}</div>` : ''}${personalCare ? `<div class="card pad" style="margin-top:17px"><div class="surface-header"><div><h3>Personal care</h3><p>Dignity-sensitive · not exportable</p></div></div>${personalCare}</div>` : ''}${mood ? `<div class="card pad" style="margin-top:17px"><div class="surface-header"><div><h3>Mood notes</h3><p>Dignity-sensitive · not exportable</p></div></div>${mood}</div>` : ''}<div class="card pad" style="margin-top:17px"><h3 style="font-size:13px;margin:0 0 8px">Need the full picture?</h3><p style="font-size:11px;color:var(--muted);line-height:1.5;margin:0 0 13px">Ask ${esc(card.elder.first_name)} or her family. Your shift card is intentionally not a full profile.</p><button class="btn ghost" data-action="search">Search care notes →</button></div></div></div></div>`;
}

export function coverage(week) {
  const isElder = state.role === 'elder';

  const rows = week.days.map(day => {
    const cells = [];
    day.open_shifts.forEach(s => {
      cells.push(`<tr><td class="date-cell"><strong>${esc(day.label)}</strong><span>${esc(day.weekday)}</span></td><td>${clock(s.start)} – ${clock(s.end)}</td><td><span class="gap">Nobody assigned</span></td><td><span class="gap">Gap</span></td></tr>`);
    });
    day.shifts.forEach(s => {
      const status = s.warning
        ? `<span class="gap">Check preference</span>`
        : s.mine ? '<span class="status">Your shift</span>' : `<span class="status">${esc(s.label || 'Covered')}</span>`;
      cells.push(`<tr><td class="date-cell"><strong>${esc(day.label)}</strong><span>${esc(day.weekday)}</span></td><td>${clock(s.start)} – ${clock(s.end)}</td><td><div class="covered">${avatar({ initials: s.caregiver_name.split(' ').map(w => w[0]).join('').slice(0, 2) })}<span>${esc(s.caregiver_name)}</span></div>${s.warning ? `<div style="font-size:9px;color:#9a6e35;margin-top:4px">${esc(s.warning)}</div>` : ''}</td><td>${status}</td></tr>`);
    });
    if (!cells.length) {
      const covering = day.hidden_count
        ? `<span class="status invited">${day.hidden_count} shift${day.hidden_count === 1 ? '' : 's'} covered by someone else</span>`
        : '<span class="gap">Nobody is covering this day</span>';
      cells.push(`<tr><td class="date-cell"><strong>${esc(day.label)}</strong><span>${esc(day.weekday)}</span></td><td>—</td><td>${covering}</td><td>${day.is_gap ? '<span class="gap">Gap</span>' : '<span class="status invited">Not your shift</span>'}</td></tr>`);
    }
    return cells.join('');
  }).join('');

  const openLabel = `${week.uncovered_day_count} day${week.uncovered_day_count === 1 ? '' : 's'} open`;
  const head = isElder
    ? `<p class="eyebrow">Your week</p><h1 class="page-title">Who is coming</h1><p class="page-subtitle">The people who will be in your home this week, and the days nobody has taken yet.</p><div class="section-head"><div><h2>Coming week</h2><p>You can see every shift, because this is your home</p></div><span class="status">${openLabel}</span></div>`
    : `<p class="eyebrow">Plan ahead</p><h1 class="page-title">Coverage</h1><p class="page-subtitle">Seven days of care, with gaps made visible before they become emergencies.</p><div class="section-head"><div><h2>Coming week</h2><p>You see your own shifts by name. Whether a day is staffed at all is a fact about ${esc((state.elder || {}).first_name || 'Amira')}, so you see that too.</p></div><span class="status">${openLabel}</span></div>`;

  const note = isElder
    ? `<div class="note" style="margin-top:17px"><b>Why this matters:</b> the person being cared for is usually the last to know who is coming. Here, ${esc((state.elder || {}).first_name || 'Amira')} sees it first.</div>`
    : `<div class="note" style="margin-top:17px"><b>Why this matters:</b> a group chat can miss a quiet Thursday. CareCircle shows the gap before it becomes a missed handoff.</div>`;

  return `<div class="content">${head}<div class="card coverage-wrap"><table class="coverage"><thead><tr><th>Day</th><th>Shift</th><th>Covering</th><th>Status</th></tr></thead><tbody>${rows}</tbody></table></div>${note}</div>`;
}
