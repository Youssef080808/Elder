import { JSDOM } from 'jsdom';

const dom = new JSDOM('<!doctype html><html><body><div id="app"></div><div id="toast"></div></body></html>', {
  url: 'http://localhost/',
  runScripts: 'dangerously',
  resources: 'usable'
});

global.window = dom.window;
global.document = dom.window.document;
global.localStorage = dom.window.localStorage;

const { render } = await import('./js/render.js');
// NOTE: import as a namespace, not destructured — destructuring a dynamic
// import() takes a one-time snapshot, and store.js's `resetState` reassigns
// (rather than mutates) `state`, so a destructured reference would go stale.
// Reading `store.state` off the namespace object stays live.
const store = await import('./js/store.js');
const state = new Proxy({}, { get: (_, k) => store.state[k] });

function click(selector) {
  const el = document.querySelector(selector);
  if (!el) throw new Error(`Not found: ${selector}`);
  el.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }));
}

function checkNoLeakedTemplateArtifacts(label) {
  const html = document.querySelector('#app').innerHTML;
  if (html.includes('undefined') || html.includes('[object Object]') || html.includes('NaN')) {
    throw new Error(`${label}: leaked artifact found in output`);
  }
}

console.log('1. Initial render (login)...');
render();
checkNoLeakedTemplateArtifacts('login');
if (!document.querySelector('[data-role="elder"]')) throw new Error('login role cards missing');
console.log('   OK — login renders, compare-strip present:', document.querySelector('.compare-strip') !== null);

console.log('2. Click into elder view...');
click('[data-role="elder"]');
checkNoLeakedTemplateArtifacts('elder overview');
if (state.screen !== 'overview') throw new Error('did not land on overview');
console.log('   OK — overview screen active');

console.log('3. Visit every elder nav screen...');
for (const screen of ['permissions', 'workload', 'preferences', 'activity', 'overview']) {
  click(`[data-screen="${screen}"]`);
  checkNoLeakedTemplateArtifacts(screen);
  if (state.screen !== screen) throw new Error(`nav to ${screen} failed`);
  console.log(`   OK — ${screen}`);
}

console.log('4. Workload screen sanity...');
click('[data-screen="workload"]');
const workloadHtml = document.querySelector('#app').innerHTML;
if (!workloadHtml.includes('32h') || !workloadHtml.includes('Fatima Rahman')) throw new Error('workload numbers missing');
console.log('   OK — workload shows hours per person');

console.log('5. Toggle a permission...');
click('[data-screen="permissions"]');
const before = state.permissions.sara.length;
click('[data-toggle="sara|mood_notes"]');
checkNoLeakedTemplateArtifacts('after toggle');
if (state.permissions.sara.length === before) throw new Error('toggle did not change permissions');
console.log('   OK — toggle updated permissions, log:', state.logs[0].text);

console.log('6. Apply a preset...');
click('[data-preset="close_family"]');
if (state.permissions.fatima.length !== 6) throw new Error('preset did not apply');
console.log('   OK — preset applied');

console.log('7. Proxy modal flow...');
click('[data-action="proxy"]');
if (!document.querySelector('#modal')) throw new Error('proxy modal did not open');
click('[data-save-proxy]');
if (state.proxy !== 'omar') throw new Error('proxy not set');
console.log('   OK — proxy appointed, log:', state.logs[0].text);

console.log('8. Proxy lock check...');
click('[data-screen="permissions"]');
const lockedBtn = document.querySelector('[data-toggle="omar|meds_schedule"]');
if (!lockedBtn.disabled) throw new Error('proxy column should be locked');
console.log('   OK — proxy cannot edit own column');

console.log('9. Switch to caregiver view...');
click('[data-action="switch"]');
checkNoLeakedTemplateArtifacts('caregiver shift');
if (state.role !== 'caregiver') throw new Error('did not switch to caregiver');
console.log('   OK — caregiver shift view renders');

console.log('10. Mark meds given + write handoff...');
click('[data-action="meds"]');
if (!state.medsGiven) throw new Error('meds not marked');
click('[data-action="handoff"]');
document.querySelector('#handoff-input').value = 'Test handoff note';
click('[data-save-handoff]');
if (state.handoff !== 'Test handoff note') throw new Error('handoff not saved');
console.log('   OK — meds + handoff recorded');

console.log('11. Coverage screen...');
click('[data-screen="coverage"]');
checkNoLeakedTemplateArtifacts('coverage');
console.log('   OK — coverage renders');

console.log('12. Persistence check — simulate reload...');
const savedRaw = localStorage.getItem('carecircle_state_v1');
if (!savedRaw) throw new Error('nothing persisted to localStorage');
const saved = JSON.parse(savedRaw);
if (saved.handoff !== 'Test handoff note' || saved.proxy !== 'omar') throw new Error('persisted state incomplete');
console.log('   OK — state persisted correctly:', Object.keys(saved).join(', '));

console.log('13. Logout...');
click('[data-action="logout"]');
if (state.role !== null) throw new Error('logout did not clear role');
checkNoLeakedTemplateArtifacts('post-logout login');
console.log('   OK — logout returns to login');

console.log('14. Reset demo...');
click('[data-role="elder"]');
click('[data-screen="permissions"]');
document.querySelectorAll('[data-action="reset"]')[0].dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }));
click('[data-save-reset]');
if (state.proxy !== null || state.handoff !== '') throw new Error('reset did not clear demo state');
console.log('   OK — reset restores defaults');

console.log('\nALL CHECKS PASSED');
