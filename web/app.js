/* Street Lighting — application controller.
 * Copyright (C) 2026 Emad Roshandel — GPL-3.0-or-later (see LICENSE)
 */
import { $, $$, api, startEngine, engineMode, fmt, esc, toast, download, downloadDataURL, readFile, legendSVG,
  niceLevels, clamp, robustMax, panZoom } from './util.js';
import { Street3D } from './view3d.js';
import * as D from './drawings.js';
import { openReport } from './report.js';
import { decorate, initHelp, qm } from './help.js';
import * as C from './charts.js';

const STEPS = [
  ['lum', 'Luminaire'], ['road', 'Road'], ['route', 'Route'], ['design', 'Design'], ['results', 'Results'],
  ['layout', 'On the route'], ['elec', 'Electrical'], ['struct', 'Columns'], ['energy', 'Energy'],
  ['report', 'Report'],
];
const KINDS = ['carriageway', 'footway', 'verge', 'median', 'cycleway', 'parking', 'shoulder'];
const TEMPLATES = {
  motorway: [['shoulder', 3, null, ''], ['carriageway', 11.25, 3, 'M1'], ['median', 4, null, ''], ['carriageway', 11.25, 3, 'M1'], ['shoulder', 3, null, '']],
  expressway: [['verge', 2, null, ''], ['carriageway', 7.5, 2, 'M2'], ['median', 3, null, ''], ['carriageway', 7.5, 2, 'M2'], ['verge', 2, null, '']],
  arterial: [['footway', 3, null, 'P2'], ['carriageway', 10.5, 3, 'M3'], ['footway', 3, null, 'P2']],
  collector: [['footway', 2.5, null, 'P4'], ['verge', 1, null, ''], ['carriageway', 7, 2, 'M4'], ['verge', 1, null, ''], ['footway', 2.5, null, 'P4']],
  residential: [['footway', 1.8, null, 'P4'], ['carriageway', 6, 2, 'P4'], ['footway', 1.8, null, 'P4']],
  pedestrian: [['footway', 10, null, 'P2']],
  cycleway: [['verge', 1, null, ''], ['cycleway', 3, null, 'P4'], ['verge', 1, null, '']],
  rural: [['verge', 1.5, null, ''], ['carriageway', 7, 2, 'M5'], ['verge', 1.5, null, '']],
};

let META = null;
let P = null;            // the project (saved as JSON)
const R = {};            // results of this session
const LUM = {};          // luminaire summaries by key
let step = 'lum', view = '3d', v3 = null;
let viewMode = 'night', viewQty = 'L', colourScale = 'classic';

// ---------------------------------------------------------------------------
// start-up
// ---------------------------------------------------------------------------
(async function main() {
  try {
    const mode = await startEngine((msg, pct) => { $('#bootMsg').textContent = msg; $('#bootBar').style.width = pct + '%'; });
    $('#engineMode').textContent = mode === 'server' ? 'desktop engine' : 'in-browser engine';
    META = await api('/meta', {});
  } catch (e) {
    $('#bootMsg').textContent = 'The calculation engine could not start: ' + e.message +
      '. Open the application with "Run Street Lighting" or check the internet connection for the online version.';
    return;
  }
  P = loadLocal() || await loadExample();
  $('#projName').value = P.name || 'New project';
  v3 = new Street3D($('#v3d'));
  wireChrome();
  initHelp();
  new MutationObserver(() => decorate($('#panel'))).observe($('#panel'), { childList: true, subtree: true });
  renderSteps();
  go('lum');
  await refreshLuminaires();
  if (step === 'lum') pageLum();
  setView('diagram');
  const b = $('#boot');
  b.style.opacity = 0;
  setTimeout(() => b.remove(), 450);
})();

async function loadExample() {
  try {
    const r = await fetch('../examples/urban_street.json');
    if (r.ok) return await r.json();
  } catch (e) { /* ignore */ }
  return { name: 'New project', luminaires: {}, maintenance: { mode: 'direct', fM: 0.8 },
    section: { elements: TEMPLATES.collector.map(mk) }, search: {}, route: { mode: 'straight', length: 400, features: {} } };
}
function mk([kind, width, lanes, cls]) {
  const e = { kind, name: D.kindLabel(kind), width };
  if (lanes) { e.lanes = lanes; e.surface = 'R3'; }
  if (cls) e.cls = cls;
  return e;
}
function loadLocal() {
  try { const s = localStorage.getItem('sl.project'); return s ? JSON.parse(s) : null; } catch (e) { return null; }
}
let saveT = null;
function save() {
  clearTimeout(saveT);
  saveT = setTimeout(() => { try { localStorage.setItem('sl.project', JSON.stringify(P)); } catch (e) { /* storage full or blocked */ } }, 300);
}

function wireChrome() {
  $('#projName').addEventListener('input', e => { P.name = e.target.value; save(); });
  $('#btnHelp').onclick = () => {
    document.body.classList.toggle('helpall');
    $('#btnHelp').classList.toggle('on', document.body.classList.contains('helpall'));
  };
  $('#btnSave').onclick = () => download((P.name || 'project').replace(/\s+/g, '_') + '.json', JSON.stringify(P, null, 1), 'application/json');
  $('#btnOpen').onclick = () => $('#fileOpen').click();
  $('#fileOpen').onchange = async e => {
    const f = e.target.files[0];
    if (!f) return;
    try {
      P = JSON.parse(await f.text());
      for (const k of Object.keys(R)) delete R[k];
      $('#projName').value = P.name || '';
      save();
      await refreshLuminaires();
      go('lum');
      toast('Opened ' + f.name, 'ok');
    } catch (err) { toast('That file is not a Street Lighting project: ' + err.message, 'error'); }
  };
  $$('#vtabs > button').forEach(b => b.onclick = () => setView(b.dataset.v));
  // WAI-ARIA tabs: one tab in the Tab order, arrow keys / Home / End move between tabs
  $('#vtabs').addEventListener('keydown', e => {
    const tabs = $$('#vtabs > button[role=tab]');
    const i = tabs.indexOf(document.activeElement);
    if (i < 0) return;
    const j = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: tabs.length - 1 }[e.key];
    if (j === undefined) return;
    e.preventDefault();
    const t = tabs[(j + tabs.length) % tabs.length];
    setView(t.dataset.v); t.focus();
  });
  $$('#modeSeg button').forEach(b => b.onclick = () => {
    viewMode = b.dataset.m;
    $$('#modeSeg button').forEach(x => { x.classList.toggle('on', x === b); x.setAttribute('aria-pressed', x === b); });
    refreshView();
  });
  $$('#qtySeg button').forEach(b => b.onclick = () => {
    viewQty = b.dataset.q;
    $$('#qtySeg button').forEach(x => { x.classList.toggle('on', x === b); x.setAttribute('aria-pressed', x === b); });
    refreshView();
  });
  $$('.v3dtools [data-cam]').forEach(b => b.onclick = () => v3.view(b.dataset.cam));
  $('#cones').onchange = e => { v3.showCones = e.target.checked; v3.build(v3.data, false); };
  $('#shot').onclick = () => downloadDataURL('street_view.png', v3.snapshot());
}

function renderSteps() {
  const idx = STEPS.findIndex(s => s[0] === step);
  $('#steps').innerHTML = STEPS.map(([k, l], i) =>
    `<button data-s="${k}" class="${k === step ? 'on' : ''} ${i < idx ? 'done' : ''}" title="Step ${i + 1}: ${l}"
      aria-label="Step ${i + 1} of ${STEPS.length}: ${l}${i < idx ? ' (visited)' : ''}" ${k === step ? 'aria-current="step"' : ''}><i aria-hidden="true">${i + 1}</i><span>${l}</span></button>`).join('');
  $$('#steps button').forEach(b => b.onclick = () => { go.byUser = true; go(b.dataset.s); });
  fitSteps();
}
// when the ten steps do not fit the top bar, drop the names of the steps farthest from the current
// one until they fit (numbers stay; the full name is in the tooltip and for screen readers)
function fitSteps() {
  const s = $('#steps');
  const bs = $$('#steps button');
  bs.forEach(b => b.classList.remove('nolab'));
  const cur = Math.max(0, bs.findIndex(b => b.classList.contains('on')));
  const order = bs.map((b, i) => i).filter(i => i !== cur).sort((a, b) => Math.abs(b - cur) - Math.abs(a - cur) || b - a);
  for (const i of order) {
    if (s.scrollWidth <= s.clientWidth + 1) break;
    bs[i].classList.add('nolab');
  }
  const on = $('#steps button.on');
  if (on) on.scrollIntoView({ block: 'nearest', inline: 'nearest' });
}
window.addEventListener('resize', () => { clearTimeout(fitSteps.t); fitSteps.t = setTimeout(fitSteps, 120); });

function go(s) {
  const tg = performance.now();
  step = s;
  renderSteps();
  const fn = { lum: pageLum, road: pageRoad, route: pageRoute, design: pageDesign, results: pageResults,
    layout: pageLayout, elec: pageElec, struct: pageStruct, energy: pageEnergy, report: pageReport }[s];
  $('#panel').scrollTop = 0;
  fn();
  const h2 = $('#panel h2');
  if (h2 && go.byUser) { h2.tabIndex = -1; h2.focus({ preventScroll: true }); }
  go.byUser = false;
  const prefer = { lum: 'diagram', road: 'xsec', route: 'route', design: '3d', results: '3d', layout: '3d',
    elec: 'route', struct: 'diagram', energy: 'diagram', report: '3d' }[s];
  if (prefer) setView(prefer);
  if (window.SL_DEBUG) console.log('go', s, (performance.now() - tg).toFixed(0), 'ms');
}

function setView(v) {
  view = v;
  $$('#vtabs > button').forEach(b => { const on = b.dataset.v === v; b.classList.toggle('on', on); b.setAttribute('aria-selected', on); b.tabIndex = on ? 0 : -1; });
  $$('.vpane').forEach(p => p.classList.toggle('on', p.id === 'v' + v));
  refreshView();
}

function busy(msg, pct) {
  if ($('#busy').hidden) announce(msg);
  $('#busy').hidden = false;
  $('#busyMsg').textContent = msg;
  $('#busyBar').style.width = (pct ?? 30) + '%';
}
function idle() { $('#busy').hidden = true; announce('Calculation finished.'); }
// screen-reader announcement through a live region that is always in the page
function announce(msg) { const a = $('#announce'); a.textContent = ''; setTimeout(() => { a.textContent = msg; }, 50); }
async function run(msg, fn) {
  busy(msg, 25);
  await new Promise(r => setTimeout(r, 30));
  try { return await fn(); } catch (e) { toast(e.message, 'error', 8000); console.error(e); return null; } finally { idle(); }
}

// ---------------------------------------------------------------------------
// shared UI helpers
// ---------------------------------------------------------------------------
const num = (id, v, step = 'any', attrs = '') => `<input type="number" id="${id}" value="${v ?? ''}" step="${step}" ${attrs}>`;
const field = (label, input, hint = '') => `<label class="f"><span>${label}${hint ? ' <small>' + hint + '</small>' : ''}</span>${input}</label>`;
const sel = (id, opts, v) => `<select id="${id}">${opts.map(o => { const [k, l] = Array.isArray(o) ? o : [o, o];
  return `<option value="${esc(k)}" ${String(k) === String(v) ? 'selected' : ''}>${esc(l)}</option>`; }).join('')}</select>`;
const val = id => { const el = document.getElementById(id); return el ? el.value : undefined; };
const fval = (id, d = 0) => { const v = parseFloat(val(id)); return Number.isFinite(v) ? v : d; };
const listNums = (s) => String(s || '').split(/[,;\s]+/).filter(x => x.trim() !== '').map(Number).filter(Number.isFinite);
const verdict = (ok, txtOk = 'Complies', txtBad = 'Does not comply') =>
  `<span class="verdict ${ok ? 'ok' : 'bad'}">${ok ? '✓ ' + txtOk : '✕ ' + txtBad}</span>`;
function nav(prev, next, nextLabel) {
  return `<div class="row" style="justify-content:space-between;margin-top:26px">
    ${prev ? `<button class="btn2" data-go="${prev}">Back</button>` : '<span></span>'}
    ${next ? `<button class="btn" data-go="${next}">${nextLabel || 'Next'}</button>` : ''}</div>`;
}
// undo for removals: keep a copy of the project and the luminaire summaries, restore on request
// the results (R) are kept too: undoing returns to exactly the state before, calculations included
function snapshot() { return { P: JSON.parse(JSON.stringify(P)), LUM: { ...LUM }, R: { ...R } }; }
function undoable(msg, before) {
  toast(msg, 'info', 7000, { label: 'Undo', fn: () => {
    P = before.P; Object.assign(LUM, before.LUM);
    for (const k of Object.keys(R)) delete R[k];
    Object.assign(R, before.R);
    save(); go(step); refreshView();
  } });
}
function bindNav() { $$('#panel [data-go]').forEach(b => b.onclick = () => { go.byUser = true; go(b.dataset.go); }); }
// an empty state that says what is missing and takes you there
const need = (msg, to, label) => `<div class="box bad need"><span>${msg}</span><button class="btn sm" data-go="${to}">${label}</button></div>`;
function classOptions(kind) {
  const c = META.classes.EN13201;
  const rp = META.classes.RP8;
  const std = P.standard || 'EN13201';
  const none = [['', '–']];
  if (std === 'RP8') {
    const list = kind === 'carriageway' ? [...rp.luminance, ...rp.illuminance] : rp.walkway;
    return none.concat(list.map(n => ['RP8:' + n, n]));
  }
  if (kind === 'carriageway') return none.concat([...c.M, ...c.C, ...c.P].map(x => [x, x]));
  return none.concat([...c.P, ...c.C, ...c.HS].map(x => [x, x]));
}
function elements() { return P.section.elements; }
function edgesOf(el) { let y = 0; return el.map(e => { const a = y; y += +e.width || 0; return [a, y]; }); }

// ---------------------------------------------------------------------------
// step 1 — luminaires
// ---------------------------------------------------------------------------
async function refreshLuminaires() {
  for (const k of Object.keys(P.luminaires || {})) {
    if (!LUM[k]) {
      try { LUM[k] = await api('/luminaire', { spec: P.luminaires[k] }); } catch (e) { toast(k + ': ' + e.message, 'error'); }
    }
  }
}

function pageLum() {
  const lib = P.luminaires || (P.luminaires = {});
  const inSearch = new Set((P.search || {}).phots || Object.keys(lib));
  const m = P.maintenance || (P.maintenance = { mode: 'direct', fM: 0.8 });
  const lt = META.lamp_types, op = META.optics;
  $('#panel').innerHTML = `
    <h2>Luminaire</h2>
    <p class="lead">Load the manufacturer's photometric file (IES or EULUMDAT). If you only know the lamp —
    an old sodium or mercury lamp, say — describe it below and a generic optic is used for an indicative design.</p>
    <h3>Photometric file ${qm('lum.file')}</h3>
    <div class="drop" id="drop">Drop .ies / .ldt files here or click to choose<input type="file" id="lumFile" accept=".ies,.ldt,.IES,.LDT" multiple hidden></div>
    <h3>Describe a lamp instead</h3>
    <div class="grid2">
      ${field('Light source', sel('gLamp', Object.entries(lt).map(([k, v]) => [k, v.label]), 'LED'))}
      ${field('Optic', sel('gOptic', Object.entries(op), 'type3'))}
      ${field('Lamp flux', num('gFlux', 12000, 100), 'lm')}
      ${field('System power', num('gPower', '', 1, 'placeholder="from typical efficacy"'), 'W')}
      ${field('Colour temperature', num('gCct', '', 100, 'placeholder="typical"'), 'K')}
      ${field('Name', '<input type="text" id="gName" placeholder="e.g. Existing 150 W SON">')}
    </div>
    <div class="row end" style="margin-top:8px"><button class="btn2" id="gAdd">Add this lamp</button></div>
    <h3>Luminaires in this project</h3>
    <div id="lumList">${Object.keys(lib).length ? '' : '<p class="note">None yet.</p>'}
    ${Object.entries(lib).map(([k, s]) => lumCard(k, s, inSearch.has(k))).join('')}</div>
    <h3>Maintenance factor ${qm('mf.mode')}</h3>
    <p class="note">Every lighting class is a maintained value: the design light output is reduced by the
    maintenance factor f<sub>M</sub> = LLMF × LSF × LMF (CIE 154).</p>
    <div class="chips">${['direct', 'cie154'].map(x => `<button class="chip ${m.mode === x || (x === 'direct' && m.mode !== 'cie154') ? 'on' : ''}" data-mm="${x}">${x === 'direct' ? 'Enter a value' : 'Calculate (CIE 154)'}</button>`).join('')}</div>
    ${m.mode === 'cie154' ? `<div class="grid2">
      ${field('Light source', sel('mLamp', Object.keys(lt), m.lamp || 'LED'))}
      ${field('Cleaning interval', num('mInt', m.interval ?? 3, 0.5), 'years')}
      ${field('Pollution', sel('mPol', [['low', 'Low (rural)'], ['medium', 'Medium (suburban)'], ['high', 'High (industrial)']], m.pollution || 'medium'))}
      ${field('Optic protection', sel('mIp', ['IP66', 'IP65', 'IP55', 'IP54', 'IP44', 'IP23'], m.ip || 'IP66'))}
      ${field('Lamp replacement every', num('mRel', m.relamp ?? m.interval ?? 3, 0.5), 'years (discharge lamps)')}
      <label class="chk" style="align-self:end"><input type="checkbox" id="mSpot" ${m.spot !== false ? 'checked' : ''}> failed lamps replaced promptly (spot)</label>
      ${field('LED rated life', num('mLh', m.l_hours ?? 100000, 1000), 'h')}
      ${field('Flux at rated life', num('mLx', m.l_x ?? 0.9, 0.01), 'L-ratio')}
      ${field('Design life', num('mLife', m.life ?? 100000, 1000), 'h')}
      ${field('Burning hours / year', num('mHrs', m.hours ?? 4100, 100), 'h')}
    </div><div class="row end"><button class="btn2" id="mCalc">Calculate</button></div>` :
    `<div class="grid2">${field('Overall maintenance factor f<sub>M</sub>', num('mF', m.fM ?? 0.8, 0.01, 'min="0.3" max="1"'))}</div>`}
    <div class="box acc small" id="mOut">${m.result ? mfText(m.result) : 'Using f<sub>M</sub> = ' + fmt(m.fM ?? 0.8, 2)}</div>
    ${nav(null, 'road', 'Next: the road')}`;
  bindNav();
  const drop = $('#drop');
  drop.onclick = () => $('#lumFile').click();
  drop.ondragover = e => { e.preventDefault(); drop.classList.add('over'); };
  drop.ondragleave = () => drop.classList.remove('over');
  drop.ondrop = e => { e.preventDefault(); drop.classList.remove('over'); addFiles(e.dataTransfer.files); };
  $('#lumFile').onchange = e => addFiles(e.target.files);
  $('#gAdd').onclick = async () => {
    const lamp = val('gLamp');
    const key = 'g' + Date.now().toString(36);
    const spec = { source: 'generic', lamp_type: lamp, optic: val('gOptic'), lamp_flux: fval('gFlux', 10000),
      dimmable: lamp === 'LED', dim_min: 0.3 };
    if (val('gPower')) spec.power = fval('gPower');
    if (val('gCct')) spec.cct = fval('gCct');
    spec.name = val('gName') || `${META.lamp_types[lamp].label} ${fmt(spec.lamp_flux, 0)} lm`;
    await addSpec(key, spec);
  };
  $$('[data-mm]').forEach(b => b.onclick = () => { m.mode = b.dataset.mm; save(); pageLum(); });
  if ($('#mF')) $('#mF').onchange = () => { m.fM = clamp(fval('mF', 0.8), 0.3, 1); delete m.result; save(); $('#mOut').innerHTML = 'Using f<sub>M</sub> = ' + fmt(m.fM, 2); invalidate('design'); };
  if ($('#mCalc')) $('#mCalc').onclick = async () => {
    Object.assign(m, { lamp: val('mLamp'), interval: fval('mInt', 3), pollution: val('mPol'), ip: val('mIp'),
      relamp: fval('mRel', 3), spot: $('#mSpot').checked,
      l_hours: fval('mLh', 1e5), l_x: fval('mLx', 0.9), life: fval('mLife', 1e5), hours: fval('mHrs', 4100) });
    const r = await run('Calculating the maintenance factor…', () => api('/maintenance', m));
    if (r) { m.result = r; m.fM = r.fM; save(); $('#mOut').innerHTML = mfText(r); invalidate('design'); }
  };
  $$('#lumList [data-lk]').forEach(el => {
    const k = el.dataset.lk;
    el.querySelector('[data-act=rm]').onclick = () => {
      const before = snapshot();
      const nm = (LUM[k] && LUM[k].name) || 'the luminaire';
      delete P.luminaires[k]; delete LUM[k];
      if (P.search && P.search.phots) P.search.phots = P.search.phots.filter(x => x !== k); save(); pageLum(); refreshView();
      undoable('Removed ' + nm + '.', before);
    };
    el.querySelector('[data-act=use]').onchange = e => {
      const s = new Set((P.search || (P.search = {})).phots || Object.keys(P.luminaires));
      e.target.checked ? s.add(k) : s.delete(k);
      P.search.phots = [...s]; save();
    };
    el.querySelector('[data-act=dim]').onchange = e => { P.luminaires[k].dimmable = e.target.checked; save(); };
    el.querySelector('[data-act=price]').onchange = e => { P.luminaires[k].price = +e.target.value; (P.costs || (P.costs = {})).luminaire = Object.fromEntries(Object.entries(P.luminaires).filter(([, s]) => s.price).map(([kk, s]) => [kk, s.price])); save(); };
  });
}
function mfText(r) { return `f<sub>M</sub> = <b>${fmt(r.fM, 3)}</b> = LLMF ${fmt(r.LLMF, 3)} × LSF ${fmt(r.LSF, 2)} × LMF ${fmt(r.LMF, 3)} <span class="note">— ${esc(r.note)}</span>`; }

function lumCard(k, s, use) {
  const i = LUM[k];
  return `<div class="box lumcard" data-lk="${k}">
    <div><div class="nm">${esc(s.name || i?.name || k)}</div>
    <div class="meta">${i ? `${fmt(i.luminaire_flux, 0)} lm · ${fmt(i.power, 0)} W · ${fmt(i.efficacy, 0)} lm/W · ${esc(i.lamp_type)} ${fmt(i.cct, 0)} K · ${i.gstar.cls} · ${i.glare.cls}` : 'reading…'}
    ${s.source === 'generic' ? ' · <b>generic optic</b>' : ''}</div></div>
    <button class="iconbtn" data-act="rm" title="Remove this luminaire" aria-label="Remove this luminaire">✕</button>
    <div class="row small" style="grid-column:1/-1;margin-top:6px">
      <label class="chk"><input type="checkbox" data-act="use" ${use ? 'checked' : ''}> use in the search</label>
      <label class="chk"><input type="checkbox" data-act="dim" ${s.dimmable !== false ? 'checked' : ''}> dimmable</label>
      <label class="chk">price <input type="number" data-act="price" value="${s.price || ''}" style="width:80px" placeholder="auto"></label>
    </div></div>`;
}

async function addFiles(files) {
  for (const f of files) {
    const text = await readFile(f);
    const key = 'f' + Date.now().toString(36) + Math.random().toString(36).slice(2, 5);
    await addSpec(key, { source: 'file', filename: f.name, text, dimmable: true, dim_min: 0.3 });
  }
}
async function addSpec(key, spec) {
  const info = await run('Reading the photometry…', () => api('/luminaire', { spec }));
  if (!info) return;
  spec.name = spec.name || info.name;
  P.luminaires[key] = spec;
  LUM[key] = info;
  P.search = P.search || {};
  P.search.phots = [...new Set([...(P.search.phots || []), key])];
  save();
  pageLum();
  setView('diagram');
  toast('Added ' + spec.name, 'ok');
  if (info.notes && info.notes.length) toast(info.notes.join(' '), 'info', 7000);
}

// ---------------------------------------------------------------------------
// step 2 — road cross-section
// ---------------------------------------------------------------------------
let selStrip = null;
function pageRoad() {
  const el = elements();
  const std = P.standard || 'EN13201';
  $('#panel').innerHTML = `
    <h2>Road</h2>
    <p class="lead">Build the cross-section from the strips of the road, left to right as drawn. Give every
    strip people use a lighting class; the drawing on the right follows your edits.</p>
    ${field('Standard', sel('std', [['EN13201', 'EN 13201 (CEN / CIE)'], ['RP8', 'ANSI/IESNA RP-8-00 (superseded edition)']], std))}
    <h3>Start from a road type ${qm('road.template')}</h3>
    <div class="chips">${Object.keys(TEMPLATES).map(k => `<button class="chip" data-tpl="${k}">${(META.road_types.find(r => r.key === k) || { label: k }).label}</button>`).join('')}</div>
    <h3>Strips</h3>
    <div class="strip head"><span></span><span>Type${qm('strip.kind')}</span><span>Width${qm('strip.width')}</span><span>Lanes${qm('strip.lanes')}</span><span>Class${qm('strip.cls')}</span><span>Surface${qm('strip.surface')}</span><span></span></div>
    ${el.map((e, i) => `<div class="strip" data-i="${i}">
      <span class="sw" style="background:${D.stripColour(e.kind)}"></span>
      <span data-l="Type">${sel('k' + i, KINDS.map(k => [k, D.kindLabel(k)]), e.kind).replace('<select ', `<select aria-label="Strip ${i + 1} type" `)}</span>
      <span data-l="Width m">${num('w' + i, e.width, 0.05, `min="0" aria-label="Strip ${i + 1} width, m"`)}</span>
      <span ${e.kind === 'carriageway' ? 'data-l="Lanes"' : ''}>${e.kind === 'carriageway' ? num('l' + i, e.lanes || 2, 1, `min="1" max="6" aria-label="Strip ${i + 1} lanes"`) : ''}</span>
      <span data-l="Class">${sel('c' + i, classOptions(e.kind), e.cls || '').replace('<select ', `<select aria-label="Strip ${i + 1} lighting class" `)}</span>
      <span ${e.kind === 'carriageway' ? 'data-l="Surface"' : ''}>${e.kind === 'carriageway' ? sel('s' + i, ['R1', 'R2', 'R3', 'R4'], e.surface || 'R3').replace('<select ', `<select aria-label="Strip ${i + 1} road surface" `) :
        `<label class="chk small" title="Facial recognition needed (adds vertical and semi-cylindrical illuminance)"><input type="checkbox" id="fc${i}" ${e.facial ? 'checked' : ''}>faces</label>${qm('strip.faces')}`}</span>
      <span><button class="iconbtn" data-rm="${i}" title="Remove strip" aria-label="Remove strip ${i + 1}">✕</button></span></div>`).join('')}
    <div class="chips" style="margin-top:8px">${KINDS.map(k => `<button class="chip" data-add="${k}">+ ${D.kindLabel(k)}</button>`).join('')}</div>
    <div class="box small">Total width <b>${fmt(el.reduce((a, e) => a + (+e.width || 0), 0), 2)} m</b>.
      Road surface: ${Object.entries(META.surfaces).map(([k, v]) => `<b>${k}</b> ${esc(v.label.split('—')[1] || '')}`).join('; ')}.</div>
    <h3>Which class? ${qm('road.classhelp')}</h3>
    <p class="note">Not sure? Answer a few questions about the traffic (CEN/TR 13201-1 method) and the class is chosen for you.</p>
    <div class="row"><button class="btn2" data-help="M">Motor traffic (M)</button><button class="btn2" data-help="C">Conflict area (C)</button><button class="btn2" data-help="P">Pedestrians (P)</button></div>
    <details class="adv"><summary>Rules applied in the design</summary>
      <div class="grid2" style="margin-top:8px">
        <label class="chk"><input type="checkbox" id="oUl" ${(P.section.options || {}).apply_Ul !== false ? 'checked' : ''}> longitudinal uniformity U<sub>l</sub></label>
        <label class="chk"><input type="checkbox" id="oREI" ${(P.section.options || {}).apply_REI !== false ? 'checked' : ''}> edge illuminance ratio R<sub>EI</sub></label>
        <label class="chk"><input type="checkbox" id="oTIP" ${(P.section.options || {}).apply_TI_P ? 'checked' : ''}> glare limit for P classes (Annex C)</label>
      </div></details>
    ${nav('lum', 'route', 'Next: the route')}`;
  bindNav();
  $('#std').onchange = e => { P.standard = e.target.value; for (const x of el) x.cls = ''; save(); pageRoad(); refreshView(); };
  $$('[data-tpl]').forEach(b => b.onclick = () => {
    const before = snapshot();
    P.section.elements = TEMPLATES[b.dataset.tpl].map(mk);
    undoable('Strips replaced by the ' + b.textContent.trim() + ' template.', before);
    if ((P.standard || 'EN13201') === 'RP8') for (const x of P.section.elements) x.cls = '';
    invalidate('design'); save(); pageRoad(); refreshView();
  });
  $$('[data-add]').forEach(b => b.onclick = () => {
    const k = b.dataset.add;
    el.push(mk([k, { carriageway: 7, footway: 2, verge: 1, median: 2, cycleway: 2, parking: 2.5, shoulder: 2.5 }[k], k === 'carriageway' ? 2 : null, '']));
    invalidate('design'); save(); pageRoad(); refreshView();
  });
  $$('[data-rm]').forEach(b => b.onclick = () => { const before = snapshot(); const [x] = el.splice(+b.dataset.rm, 1);
    invalidate('design'); save(); pageRoad(); refreshView(); undoable('Removed the ' + (x.name || x.kind) + ' strip.', before); });
  el.forEach((e, i) => {
    const on = (id, f) => { const x = document.getElementById(id); if (x) x.onchange = () => { f(x); invalidate('design'); save(); refreshView(); }; };
    on('k' + i, x => { e.kind = x.value; e.name = D.kindLabel(e.kind); if (e.kind === 'carriageway') { e.lanes = e.lanes || 2; e.surface = e.surface || 'R3'; } pageRoad(); });
    on('w' + i, x => { e.width = Math.max(0, +x.value); });
    on('l' + i, x => { e.lanes = Math.max(1, +x.value); });
    on('c' + i, x => { e.cls = x.value; });
    on('s' + i, x => { e.surface = x.value; });
    on('fc' + i, x => { e.facial = x.checked; });
    const row = document.querySelector(`.strip[data-i="${i}"]`);
    row.onfocusin = () => { selStrip = i; if (view === 'xsec') refreshView(); };
  });
  const opt = P.section.options || (P.section.options = {});
  $('#oUl').onchange = e => { opt.apply_Ul = e.target.checked; save(); invalidate('design'); };
  $('#oREI').onchange = e => { opt.apply_REI = e.target.checked; save(); invalidate('design'); };
  $('#oTIP').onchange = e => { opt.apply_TI_P = e.target.checked; save(); invalidate('design'); };
  $$('[data-help]').forEach(b => b.onclick = () => classHelper(b.dataset.help));
}

function classHelper(series) {
  const qs = META.selection[series];
  const f = $('#dlgForm');
  f.innerHTML = `<h3 id="dlgTitle">Choose a ${series} class</h3><p class="note">CEN/TR 13201-1:2014 weighting — the class number is 6 minus the sum of the weights.</p>
    ${qs.map(q => `<div class="qrow"><span>${esc(q.label)}</span>${sel('q_' + q.key, q.options.map(o => [o.key, `${o.label} (${o.w >= 0 ? '+' : ''}${o.w})`]), q.options[Math.min(1, q.options.length - 1)].key)}</div>`).join('')}
    <div class="box acc" id="qOut" style="margin-top:12px">–</div>
    <p class="small">Apply to strip: ${sel('qTarget', elements().map((e, i) => [i, `${i + 1}. ${e.name || e.kind}`]), elements().findIndex(e => (series === 'P') !== (e.kind === 'carriageway')))}</p>
    <div class="row end"><button class="btn2" value="cancel">Close</button><button class="btn" id="qApply" value="ok">Apply</button></div>`;
  const calc = async () => {
    const answers = Object.fromEntries(qs.map(q => [q.key, val('q_' + q.key)]));
    const r = await api('/class/select', { series, answers });
    $('#qOut').innerHTML = `Weight sum ${r.sum} → class <b>${r.cls}</b>${r.facial ? ' with facial-recognition requirements' : ''}<br><span class="note">${esc(r.note)}</span>`;
    f.dataset.cls = r.cls; f.dataset.facial = r.facial ? '1' : '';
  };
  $$('select', f).forEach(s => s.onchange = calc);
  calc();
  $('#qApply').onclick = () => {
    const i = +val('qTarget');
    const e = elements()[i];
    if ((P.standard || 'EN13201') !== 'EN13201') { P.standard = 'EN13201'; }
    e.cls = f.dataset.cls;
    if (series === 'P') e.facial = !!f.dataset.facial;
    save(); invalidate('design'); pageRoad(); refreshView();
  };
  $('#dlg').showModal();
}

// ---------------------------------------------------------------------------
// step 3 — route and topology
// ---------------------------------------------------------------------------
let drawing = false;
function pageRoute() {
  const r = P.route || (P.route = { mode: 'straight', length: 400, features: {} });
  if (!R.geom) loadGeometry(true).then(() => { if (view === 'route' || view === 'profile') refreshView(); });
  const ft = r.features || (r.features = {});
  const pr = r.profile || (r.profile = { pvis: [], crossfall: 0 });
  const tbl = (name, cols, rows) => `<table class="t" data-tbl="${name}"><tr>${cols.map(c => `<th>${c[1]}${qm(name + '.' + c[0])}</th>`).join('')}<th></th></tr>
    ${rows.map((row, i) => `<tr>${cols.map(c => {
      const id = `${name}_${i}_${c[0]}`, al = `aria-label="${esc(c[1])}, row ${i + 1}"`;
      // a straight has no radius, angle or turn: grey those out so it is clear what to fill in
      const na = name === 'seg' && row.type !== 'arc' && ['radius', 'angle', 'turn'].includes(c[0]) ? ' disabled placeholder="—"' : '';
      return `<td>${c[2] === 'sel' ? sel(id, c[3], row[c[0]]).replace('<select ', `<select ${al}${na} `) :
      c[2] === 'text' ? `<input type="text" id="${id}" ${al} value="${esc(row[c[0]] ?? '')}">` :
      `<input type="number" step="any" id="${id}" ${al}${na} value="${na ? '' : row[c[0]] ?? ''}">`}</td>`; }).join('')}
    <td><button class="iconbtn" data-del="${name}:${i}" aria-label="Remove row ${i + 1}" title="Remove this row">✕</button></td></tr>`).join('')}</table>
    <button class="btn2 sm" data-new="${name}">+ add</button>`;
  $('#panel').innerHTML = `
    <h2>Route</h2>
    <p class="lead">Describe where the road goes: straight, with bends, drawn on the plan or imported from a
    drawing or a map. Hills, trees, crossings and junctions change where the poles go.</p>
    <h3>How the road runs ${qm('route.mode')}</h3><div class="chips">${[['straight', 'Straight'], ['segments', 'Straights and bends'], ['points', 'Draw / import']].map(([k, l]) => `<button class="chip ${r.mode === k ? 'on' : ''}" data-mode="${k}">${l}</button>`).join('')}</div>
    ${r.mode === 'straight' ? `<div class="grid2">${field('Length', num('rLen', r.length || 400, 1), 'm')}</div>` : ''}
    ${r.mode === 'segments' ? `${tbl('seg', [['type', 'Type', 'sel', [['straight', 'Straight'], ['arc', 'Bend']]], ['length', 'Length m'], ['radius', 'Radius m'], ['angle', 'Angle °'], ['turn', 'Turn', 'sel', [['L', 'Left'], ['R', 'Right']]]], r.segments || (r.segments = []))}` : ''}
    ${r.mode === 'points' ? `
      <p class="note">Click on the <b>Route plan</b> to add points; drag a point to move it; right-click a point to delete it. Bends get the radius below.</p>
      <div class="grid2">${field('Bend radius at the points', num('rRad', r.radius ?? 80, 1), 'm')}
      ${field('Grid', sel('rGrid', [[10, '10 m'], [25, '25 m'], [50, '50 m']], r.grid || 25))}</div>
      <div class="row" style="margin-top:8px"><button class="btn2" id="rDraw">${drawing ? 'Stop drawing' : 'Draw on the plan'}</button>
      <button class="btn2" id="rClear">Clear points</button>
      <button class="btn2" id="rImp">Import DXF / GeoJSON / KML / GPX / CSV</button><input type="file" id="rFile" hidden accept=".dxf,.geojson,.json,.kml,.gpx,.csv,.txt"></div>
      <p class="note" id="ptCount">${(r.points || []).length} points${r.import_note ? ' · ' + esc(r.import_note) : ''}</p>` : ''}
    <h3>Vertical profile</h3>
    <p class="note">Elevations at points along the road (PVIs). A vertical-curve length smooths a crest or sag.</p>
    ${tbl('pvi', [['0', 'Chainage m'], ['1', 'Elevation m'], ['2', 'Curve length m']], (pr.pvis || []).map(p => ({ 0: p[0], 1: p[1], 2: p[2] || 0 })))}
    <div class="grid2" style="margin-top:8px">${field('Cross-fall', num('rCf', pr.crossfall || 0, 0.5), '% toward side B')}</div>
    <h3>Trees</h3>
    <p class="note">y is measured across the section from its first edge (side A). Crowns block light; the design reacts to them.</p>
    ${(ft.tree_lines || (ft.tree_lines = [])).map((t, i) => `<div class="box"><div class="grid3">
      ${[['y', 'Position y', 'm'], ['s0', 'From ch', 'm'], ['s1', 'To ch', 'm'], ['spacing', 'Every', 'm'], ['crown_base', 'Crown starts at', 'm'], ['height', 'Tree top', 'm'],
        ['crown_radius', 'Crown radius', 'm'], ['density', 'Foliage density', '1/m']].map(([k, l, u]) => field(l, `<input type="number" step="any" id="tree_${i}_${k}" value="${t[k] ?? ''}">`, u)).join('')}
      <div class="row end" style="align-self:end"><button class="iconbtn txt" data-del="tree:${i}" aria-label="Remove tree line ${i + 1}">✕ remove</button></div></div></div>`).join('')}
    <button class="btn2 sm" data-new="tree">+ add a tree line</button>
    <h3>Crossings, junctions and other constraints</h3>
    <h4>Pedestrian crossings</h4>${tbl('cross', [['s', 'chainage m']], ft.crossings || (ft.crossings = []))}
    <h4>Junctions</h4>${tbl('junc', [['s', 'chainage m'], ['side', 'side', 'sel', [['left', 'side A'], ['right', 'side B'], ['both', 'both']]]], ft.junctions || (ft.junctions = []))}
    <h4>No poles here (driveways, bridges, utilities)</h4>${tbl('nop', [['s0', 'from ch'], ['s1', 'to ch'], ['reason', 'reason', 'text']], ft.no_pole || (ft.no_pole = []))}
    <h4>Overhead lines</h4>${tbl('ohl', [['s0', 'from ch'], ['s1', 'to ch'], ['y', 'y m'], ['height', 'height m']], ft.overhead_lines || (ft.overhead_lines = []))}
    <div class="row" style="margin-top:14px"><button class="btn2" id="rCheck">Read the topology</button></div>
    <div id="topo">${R.geom ? topoHTML(R.geom.topology) : ''}</div>
    ${nav('road', 'design', 'Next: find the layout')}`;
  bindNav();
  $$('[data-mode]').forEach(b => b.onclick = () => { r.mode = b.dataset.mode; drawing = r.mode === 'points'; geomChanged(); pageRoute(); setView('route'); });
  if ($('#rLen')) $('#rLen').onchange = () => { r.length = Math.max(10, fval('rLen', 400)); geomChanged(); };
  if ($('#rRad')) $('#rRad').onchange = () => { r.radius = Math.max(0, fval('rRad', 80)); geomChanged(); };
  if ($('#rGrid')) $('#rGrid').onchange = () => { r.grid = +val('rGrid'); refreshView(); };
  if ($('#rDraw')) $('#rDraw').onclick = () => { drawing = !drawing; pageRoute(); setView('route'); };
  if ($('#rClear')) $('#rClear').onclick = () => { r.points = []; delete r._vb; geomChanged(); pageRoute(); refreshView(); };
  if ($('#rImp')) { $('#rImp').onclick = () => $('#rFile').click(); $('#rFile').onchange = importRoute; }
  $('#rCf').onchange = () => { pr.crossfall = fval('rCf', 0); geomChanged(); };
  $('#rCheck').onclick = async () => { await loadGeometry(); pageRoute(); setView('route'); };
  // generic table binding
  const tables = { seg: () => r.segments, tree: () => ft.tree_lines, cross: () => ft.crossings, junc: () => ft.junctions,
    nop: () => ft.no_pole, ohl: () => ft.overhead_lines };
  const defaults = { seg: { type: 'straight', length: 100 }, tree: { y: 0.5, s0: 0, s1: 200, spacing: 8, crown_base: 3.5, height: 9, crown_radius: 2.5, density: 0.6 },
    cross: { s: 100 }, junc: { s: 200, side: 'left' }, nop: { s0: 50, s1: 60, reason: 'driveway' }, ohl: { s0: 0, s1: 100, y: 0, height: 8 } };
  for (const [name, get] of Object.entries(tables)) {
    const rows = get();
    if (!rows) continue;
    rows.forEach((row, i) => {
      $$(`[id^="${name}_${i}_"]`).forEach(inp => inp.onchange = () => {
        const key = inp.id.split('_').slice(2).join('_');
        row[key] = inp.type === 'number' ? parseFloat(inp.value) : inp.value;
        geomChanged();
        if (name === 'seg' && key === 'type') pageRoute();
      });
    });
  }
  $$('[data-new]').forEach(b => b.onclick = () => {
    const name = b.dataset.new;
    if (name === 'pvi') { pr.pvis.push([pr.pvis.length ? pr.pvis[pr.pvis.length - 1][0] + 100 : 0, pr.pvis.length ? pr.pvis[pr.pvis.length - 1][1] : 0, 0]); }
    else tables[name]().push({ ...defaults[name] });
    geomChanged(); pageRoute();
  });
  $$('[data-del]').forEach(b => b.onclick = () => {
    const before = snapshot();
    const [name, i] = b.dataset.del.split(':');
    undoable('Row removed.', before);
    if (name === 'pvi') pr.pvis.splice(+i, 1); else tables[name]().splice(+i, 1);
    geomChanged(); pageRoute();
  });
  (pr.pvis || []).forEach((p, i) => [0, 1, 2].forEach(c => {
    const x = document.getElementById(`pvi_${i}_${c}`);
    if (x) x.onchange = () => { p[c] = parseFloat(x.value) || 0; pr.pvis.sort((a, b) => a[0] - b[0]); geomChanged(); };
  }));
}

function topoHTML(t) {
  if (!t || !t.length) return '<p class="note">A straight, level road — no special conditions.</p>';
  return `<div class="box acc"><b>What the route asks of the design</b><ul class="topo small">${t.map(x => `<li>${esc(x.text)}</li>`).join('')}</ul>
    <span class="note">Bends: shorter spacing and poles on the outside; crests: shorter spacing and a sharp cut-off (EN 13201-2 A.3.1); trees: lower mounting, longer arms or the other side; crossings: extra luminaires before the crossing (Annex B).</span></div>`;
}

let geomT = null;
function geomChanged() {
  save();
  const pc = $('#ptCount');
  if (pc) pc.textContent = (P.route.points || []).length + ' points';
  invalidate('layout');
  clearTimeout(geomT);
  geomT = setTimeout(async () => { await loadGeometry(true); if (view === 'route' || view === 'profile') refreshView(); }, 350);
}
async function loadGeometry(quiet) {
  const ok = P.route.mode !== 'points' || (P.route.points || []).length >= 2;
  if (!ok) { R.geom = null; return; }
  try { R.geom = await api('/route/geometry', { project: P }); }
  catch (e) { if (!quiet) toast(e.message, 'error'); R.geom = null; }
  const t = $('#topo');
  if (t && R.geom) t.innerHTML = topoHTML(R.geom.topology);
}

async function importRoute(e) {
  const f = e.target.files[0];
  if (!f) return;
  const text = await f.text();
  const r = await run('Importing the centreline…', () => api('/import/route', { text, filename: f.name, radius: P.route.radius || 0 }));
  if (!r) return;
  P.route.points = r.points.map(p => [+p[0].toFixed(3), +p[1].toFixed(3)]);
  delete P.route._vb;
  P.route.import_note = `${r.source}${r.origin ? ` (origin ${r.origin.lat0.toFixed(5)}, ${r.origin.lon0.toFixed(5)})` : ''}${r.alternatives ? `, longest of ${r.alternatives + 1} lines` : ''}`;
  if (r.profile && r.profile.length >= 2) { P.route.profile.pvis = r.profile; toast('Elevations were found and used for the profile.', 'ok'); }
  geomChanged();
  pageRoute();
  setView('route');
}

// ---------------------------------------------------------------------------
// step 4 — design search
// ---------------------------------------------------------------------------
function pageDesign() {
  const sc = P.search || (P.search = {});
  const c = P.costs || (P.costs = {});
  const cd = META.cost_defaults;
  const keys = sc.phots && sc.phots.length ? sc.phots : Object.keys(P.luminaires);
  const arrs = META.arrangements;
  const man = sc.manual || (sc.manual = { arrangement: 'single_left', H: 10, overhang: 1, tilt: 5, S: 35, flux: 1, phot: keys[0] });
  $('#panel').innerHTML = `
    <h2>Design</h2>
    <p class="lead">The search tries every arrangement, mounting height, arm length and tilt, finds the longest
    spacing that still meets every class, dims the luminaire to the level needed, and ranks the results by
    life-cycle cost.</p>
    <div class="box small">Luminaires: ${keys.map(k => `<b>${esc(P.luminaires[k]?.name || k)}</b>`).join(', ') || '<b>none — add one in step 1</b>'} ·
      f<sub>M</sub> ${fmt(P.maintenance?.fM ?? 0.8, 2)}</div>
    <h3>Search range</h3>
    <div class="grid2">
      ${field('Mounting heights', `<input type="text" id="sH" value="${(sc.heights || []).join(', ')}" placeholder="automatic from the road width">`, 'm')}
      ${field('Arm lengths', `<input type="text" id="sO" value="${(sc.overhangs || []).join(', ')}" placeholder="0, 0.5, 1, 1.5, 2">`, 'm')}
      ${field('Tilt angles', `<input type="text" id="sT" value="${(sc.tilts || []).join(', ')}" placeholder="0, 5, 10">`, '°')}
      ${field('Pole set-back from the kerb', num('sSb', sc.setback ?? 0.8, 0.1), 'm')}
    </div>
    <h4>Arrangements ${qm('design.arr')}</h4>
    <div class="chips">${Object.entries(arrs).map(([k, l]) => `<button class="chip ${(sc.arrangements || []).includes(k) ? 'on' : ''}" data-arr="${k}">${l}</button>`).join('')}</div>
    <p class="note">None selected = every arrangement that suits the cross-section.</p>
    <details class="adv"><summary>Costs used for ranking</summary><div class="grid2" style="margin-top:8px">
      ${field('Currency', `<input type="text" id="cCur" value="${esc(c.currency || cd.currency)}">`)}
      ${field('Column, fixed part', num('cPb', c.pole_base ?? cd.pole_base, 1))}
      ${field('Column, per metre height', num('cPm', c.pole_per_m ?? cd.pole_per_m, 1))}
      ${field('Arm, per metre', num('cAm', c.arm_per_m ?? cd.arm_per_m, 1))}
      ${field('Foundation + installation', num('cFd', (c.foundation ?? cd.foundation) + (c.install_per_pole ?? cd.install_per_pole), 1))}
      ${field('Luminaire, per watt', num('cLw', c.luminaire_per_w ?? cd.luminaire_per_w, 0.1))}
      ${field('Cable + trench, per metre', num('cCb', (c.cable_per_m ?? cd.cable_per_m) + (c.trench_per_m ?? cd.trench_per_m), 0.5))}
      ${field('Energy price, per kWh', num('cEp', c.energy_price ?? cd.energy_price, 0.01))}
      ${field('Burning hours / year', num('cHr', c.hours ?? cd.hours, 50))}
      ${field('Life of the scheme', num('cYr', c.years ?? cd.years, 1), 'years')}
      ${field('Discount rate', num('cDr', c.discount ?? cd.discount, 0.01))}
    </div></details>
    ${keys.length > 4 ? `<label class="chk" style="margin-top:12px"><input type="checkbox" id="sFull" ${sc.full ? 'checked' : ''}>
      search every luminaire in full (slower)</label>${qm('design.full')}
      <p class="note">${sc.full ? `All ${keys.length} luminaires are searched in full — expect several times longer.`
        : `A quick first pass ranks all ${keys.length} luminaires; the 3 most promising are then searched in full.`}</p>` : ''}
    <button class="btn big" id="btnSearch" style="margin-top:14px">Find the best layout</button>
    <div id="cands">${R.opt ? candTable() : ''}</div>
    <h3>Or check your own layout</h3>
    <div class="grid2">
      ${field('Arrangement', sel('mA', Object.entries(arrs), man.arrangement))}
      ${field('Luminaire', sel('mP', keys.map(k => [k, P.luminaires[k]?.name || k]), man.phot))}
      ${field('Mounting height', num('mH', man.H, 0.5), 'm')}
      ${field('Spacing', num('mS', man.S, 0.5), 'm')}
      ${field('Arm length', num('mO', man.overhang, 0.1), 'm')}
      ${field('Tilt', num('mT', man.tilt, 1), '°')}
      ${field('Light output', num('mF2', man.flux, 0.05, 'min="0.1" max="1.5"'), '× rated')}
    </div>
    <div class="row end" style="margin-top:8px"><button class="btn2" id="btnManual">Check this layout</button></div>
    ${nav('route', R.eval ? 'results' : null, 'See the results')}`;
  bindNav();
  $$('[data-arr]').forEach(b => b.onclick = () => {
    const s = new Set(sc.arrangements || []);
    s.has(b.dataset.arr) ? s.delete(b.dataset.arr) : s.add(b.dataset.arr);
    sc.arrangements = [...s]; save(); b.classList.toggle('on');
  });
  const readSearch = () => {
    sc.heights = listNums(val('sH')); sc.overhangs = listNums(val('sO')); sc.tilts = listNums(val('sT'));
    if (!sc.heights.length) delete sc.heights; if (!sc.overhangs.length) delete sc.overhangs; if (!sc.tilts.length) delete sc.tilts;
    sc.setback = fval('sSb', 0.8);
    if ($('#sFull')) sc.full = $('#sFull').checked;
    Object.assign(c, { currency: val('cCur'), pole_base: fval('cPb'), pole_per_m: fval('cPm'), arm_per_m: fval('cAm'),
      foundation: fval('cFd') * 0.6, install_per_pole: fval('cFd') * 0.4, luminaire_per_w: fval('cLw'),
      cable_per_m: fval('cCb') * 0.35, trench_per_m: fval('cCb') * 0.65, energy_price: fval('cEp'), hours: fval('cHr'),
      years: fval('cYr'), discount: fval('cDr') });
    save();
  };
  if ($('#sFull')) $('#sFull').onchange = () => { readSearch(); pageDesign(); };
  $('#btnSearch').onclick = async () => {
    readSearch();
    if (!Object.keys(P.luminaires).length) return toast('Add a luminaire in step 1 first.', 'error');
    const nk = keys.length;
    const msg = nk > 3 && !sc.full ? `Quick pass over ${nk} luminaires, then a full search of the best 3…`
      : nk > 3 ? `Searching all ${nk} luminaires in full… this can take a few minutes.`
      : 'Searching arrangements, heights, arms and tilts… this takes a little while.';
    const r = await run(msg, () => api('/optimize', { project: P }));
    if (!r) return;
    R.opt = r;
    invalidate('layout');
    if (r.best) { R.sel = r.candidates[0]; R.eval = r.best; }
    pageDesign();
    if (r.best) { toast(`Best: ${r.candidates[0].label}, H ${r.candidates[0].H} m, spacing ${fmt(r.candidates[0].S, 2)} m`, 'ok'); setView('3d'); refreshView(); }
    else toast((r.advice || []).join(' '), 'error', 10000);
  };
  bindCands();
  $('#btnManual').onclick = async () => {
    readSearch();
    Object.assign(man, { arrangement: val('mA'), phot: val('mP'), H: fval('mH', 10), S: fval('mS', 35), overhang: fval('mO', 0),
      tilt: fval('mT', 0), flux: fval('mF2', 1) });
    save();
    const r = await run('Calculating to EN 13201-3…', () => api('/manual', { project: P, manual: man }));
    if (!r) return;
    R.eval = r; R.sel = r.candidate; invalidate('layout');
    go('results');
  };
}

function candTable() {
  const o = R.opt;
  const cur = (P.costs || {}).currency || 'USD';
  if (!o.candidates.length) return `<div class="box bad">${(o.advice || []).map(esc).join('<br>')}</div>`;
  const nm = x => esc(x.name || x.phot);
  const scr = (o.screening || []).length ? `<details class="adv"><summary>Quick pass: ${o.screening.length} luminaires ranked, best ${o.screening.filter(x => x.searched).length} searched in full</summary>
    <table class="t small"><tr><th>Luminaire</th><th class="n">Best cost/km in the quick pass</th><th>Full search</th></tr>
    ${o.screening.map(x => `<tr><td>${nm(x)}</td><td class="n">${x.npv_km != null ? fmt(x.npv_km / 1000, 1) + 'k' : 'no compliant layout'}</td><td>${x.searched ? 'yes' : '–'}</td></tr>`).join('')}</table>
    <p class="note">Tick “search every luminaire in full” to search all of them.</p></details>` : '';
  const warn = [
    (o.no_design || []).length ? `No layout meets every class with: ${o.no_design.map(x => x.name || x.phot).join(', ')}.` : '',
    (o.incomplete || []).length ? `The search of ${o.incomplete.map(x => x.name || x.phot).join(', ')} reached its calculation limit before trying every geometry — narrow the heights, arms or tilts.` : '',
  ].filter(Boolean);
  return `<p class="note">${o.n_feasible} of ${o.n_combinations} geometries meet every class (${o.n_evaluated} calculations).
    ${(o.tree_notes || []).length ? 'Trees: ' + o.tree_notes.map(esc).join('; ') + '.' : ''}</p>${scr}
    ${warn.length ? `<p class="note">${warn.map(esc).join(' ')}</p>` : ''}
    <table class="t"><tr><th>Arrangement</th><th class="n">H</th><th class="n">Arm</th><th class="n">Tilt</th><th class="n">Spacing</th><th class="n">Output</th><th class="n">Poles/km</th><th class="n">kW/km</th><th class="n">Cost/km*</th></tr>
    ${o.candidates.map((c, i) => `<tr class="click ${R.sel && same(R.sel, c) ? 'sel' : ''}" data-ci="${i}"><td>${esc(c.label)}${o.candidates.length > 1 && new Set(o.candidates.map(x => x.phot)).size > 1 ? '<br><span class="note">' + esc(c.phot_name) + '</span>' : ''}</td>
      <td class="n">${fmt(c.H, 1)}</td><td class="n">${fmt(c.overhang, 1)}</td><td class="n">${fmt(c.tilt, 0)}°</td>
      <td class="n"><b>${fmt(c.S, 2)}</b></td><td class="n">${fmt(c.f * 100, 0)} %</td><td class="n">${fmt(c.n_poles_km, 1)}</td>
      <td class="n">${fmt(c.kw_km, 2)}</td><td class="n">${fmt(c.npv_km / 1000, 1)}k</td></tr>`).join('')}</table>
    <p class="note">* ${esc(cur)}, life-cycle cost per km (columns, luminaires, cable, energy and maintenance, discounted). Click a row to inspect it.</p>`;
}
const same = (a, b) => a.arrangement === b.arrangement && a.H === b.H && a.overhang === b.overhang && a.tilt === b.tilt && a.phot === b.phot && Math.abs(a.S - b.S) < 1e-6;
function bindCands() {
  $$('#cands [data-ci]').forEach(tr => tr.onclick = async () => {
    const c = R.opt.candidates[+tr.dataset.ci];
    const r = await run('Calculating the selected layout…', () => api('/evaluate', { project: P, candidate: c }));
    if (!r) return;
    R.sel = c; R.eval = r; invalidate('layout');
    $('#cands').innerHTML = candTable(); bindCands();
    setView('3d'); refreshView();
  });
}

function invalidate(from) {
  if (from === 'design') { delete R.opt; delete R.eval; delete R.sel; }
  if (from === 'design' || from === 'layout') { delete R.route; delete R.elec; delete R.struct; }
}

// ---------------------------------------------------------------------------
// step 5 — results of the straight section
// ---------------------------------------------------------------------------
function pageResults() {
  const e = R.eval, c = R.sel;
  if (!e) { $('#panel').innerHTML = `<h2>Results</h2><p class="lead">The results appear here once the design search has found a layout.</p>${need('No design has been calculated yet.', 'design', 'Go to step 4: Design')}${nav('design', null)}`; bindNav(); return; }
  const cur = (P.costs || {}).currency || 'USD';
  $('#panel').innerHTML = `
    <h2>Results</h2>
    <p class="lead">${esc(c.label)} · ${esc(c.phot_name || P.luminaires[c.phot]?.name || '')}</p>
    <div class="row">${verdict(e.ok, 'Every class is met', 'Some criteria are not met')}</div>
    <div class="kpis">
      <div class="kpi"><b>${fmt(c.H, 1)} m</b><span>mounting height</span></div>
      <div class="kpi"><b>${fmt(c.S, 2)} m</b><span>spacing</span></div>
      <div class="kpi"><b>${fmt(c.overhang, 1)} m · ${fmt(c.tilt, 0)}°</b><span>arm · tilt</span></div>
      <div class="kpi"><b>${fmt(c.f * 100, 0)} %</b><span>light output</span></div>
      <div class="kpi"><b>${fmt(e.energy.PDI * 1000, 1)}</b><span>PDI mW/(lx·m²)</span></div>
      <div class="kpi"><b>${fmt(e.energy.AECI / 1000, 2)}</b><span>AECI kWh/(m²·yr)</span></div>
    </div>
    <p class="small">Installed intensity class <b>${e.gstar.cls}</b> (max ${fmt(e.gstar.i80, 0)} cd/klm at 80°, ${fmt(e.gstar.i90, 0)} at 90°) ·
      glare index class <b>${e.glare.cls}</b> · f<sub>M</sub> ${fmt(e.fM, 2)}</p>
    ${e.areas.filter(a => a.cls).map(a => `
      <h3>${esc(a.name)} — ${a.cls} ${verdict(a.ok, 'meets', 'fails')}</h3>
      ${(a.checks || []).map(k => `<div class="crit"><span>${esc(k.name)} ${k.symbol ? '<i>' + esc(k.symbol) + '</i>' : ''}</span>
        <span class="v">${fmt(k.value, k.unit === '%' ? 1 : 2)} ${esc(k.unit || '')}</span><span class="rq">${k.op === '>=' ? '≥' : '≤'} ${fmt(k.req, 2)}</span>
        <span class="verdict ${k.ok ? (k.met === false ? 'adv' : 'ok') : 'bad'}">${k.ok ? (k.met === false ? 'note' : 'pass') : 'fail'}</span>
        <span class="why">${esc(k.reason)}</span></div>`).join('')}
      ${a.observers ? `<table class="t small" style="margin-top:6px"><tr><th>Observer</th><th class="n">L̄ cd/m²</th><th class="n">Uo</th><th class="n">Ul</th>${a.observers.some(o => o.TI != null) ? '<th class="n">fTI %</th>' : ''}</tr>
        ${a.observers.map(o => `<tr><td>lane ${o.lane}</td><td class="n">${fmt(o.L_avg, 2)}</td><td class="n">${fmt(o.U0, 2)}</td><td class="n">${fmt(o.Ul, 2)}</td>${o.TI != null ? `<td class="n">${fmt(o.TI, 1)}</td>` : ''}</tr>`).join('')}</table>` : ''}
      <p class="note">Ē ${fmt(a.E_avg, 2)} lx · E<sub>min</sub> ${fmt(a.E_min, 2)} lx · U<sub>o</sub>(E) ${fmt(a.U0_E, 2)}${a.Ev_min ? ` · E<sub>v,min</sub> ${fmt(a.Ev_min, 2)} · E<sub>sc,min</sub> ${fmt(a.Esc_min, 2)} lx` : ''}</p>
      ${a.REI && a.REI.skipped && Object.keys(a.REI.skipped).length ? `<p class="note">R<sub>EI</sub> not assessed on ${Object.entries(a.REI.skipped).map(([sd, why]) => (sd === 'low' ? 'side A' : 'side B') + ': ' + esc(why)).join('; ')} (EN 13201-2 Table 1 note d, EN 13201-3 8.6).</p>` : ''}`).join('')}
    <div class="box small">Cost per km (${esc(cur)}): investment ${fmt(c.capex_km, 0)}, running ${fmt(c.opex_km, 0)} per year,
      life-cycle ${fmt(c.npv_km, 0)}. ${fmt(c.n_poles_km, 1)} columns and ${fmt(c.n_lum_km, 1)} luminaires per km, ${fmt(c.kw_km, 2)} kW/km.</div>
    <div class="row" style="margin-top:10px"><button class="btn2" id="dxfSec">Drawing (DXF)</button><button class="btn2" id="csvGrid">Grid values (CSV)</button></div>
    ${nav('design', 'layout', 'Lay it out along the route')}`;
  bindNav();
  $('#dxfSec').onclick = async () => {
    const r = await run('Writing the drawing…', () => api('/export/dxf_section', { project: P, candidate: c, result: e,
      info: [P.name || '', c.label + ', H ' + c.H + ' m, S ' + fmt(c.S, 2) + ' m', 'Street Lighting ' + META.version] }));
    if (r) download(r.filename, r.text, 'application/dxf');
  };
  $('#csvGrid').onclick = () => {
    const lines = ['area,class,x_m,y_m,E_lx' + ',L_cdm2'];
    for (const a of e.areas) a.grid_y.forEach((y, j) => a.grid_x.forEach((x, i) =>
      lines.push([a.name, a.cls, x.toFixed(3), y.toFixed(3), a.grid_E[j][i], a.grid_L ? a.grid_L[j][i] : ''].join(','))));
    download('calculation_grid.csv', lines.join('\n'), 'text/csv');
  };
}

// ---------------------------------------------------------------------------
// step 6 — along the route
// ---------------------------------------------------------------------------
function pageLayout() {
  const lo = (P.route.layout = P.route.layout || { margin: 0.95, max_iter: 6 });
  const rr = R.route;
  $('#panel').innerHTML = `
    <h2>Along the route</h2>
    <p class="lead">The chosen layout is placed along the real road. Bends, crests, trees, junctions, crossings and
    no-pole zones move or add poles; then every span is calculated and tightened until it complies.</p>
    ${R.sel ? `<div class="box small">Design: ${esc(R.sel.label)}, H ${fmt(R.sel.H, 1)} m, spacing ${fmt(R.sel.S, 2)} m</div>` : need('Choose a design in step 4 first.', 'design', 'Go to step 4')}
    <div class="grid2">
      ${field('Spacing margin', num('lM', lo.margin ?? 0.95, 0.01, 'min="0.7" max="1"'), '× design spacing')}
      ${field('Crest spacing factor', num('lC', lo.crest_factor ?? 0.85, 0.05), '×')}
      ${field('Refinement rounds', num('lI', lo.max_iter ?? 6, 1, 'min="0" max="12"'))}
      ${field('Tree clearance', num('lT', lo.tree_clearance ?? 1, 0.5), 'm')}
    </div>
    <div class="grid2" style="margin-top:6px">
      <label class="chk"><input type="checkbox" id="lB" ${lo.curve_rule !== false ? 'checked' : ''}> shorter spacing on bends</label>
      <label class="chk"><input type="checkbox" id="lO" ${lo.outside_on_bends !== false ? 'checked' : ''}> poles on the outside of bends</label>
      <label class="chk"><input type="checkbox" id="lX" ${lo.extra_crossing !== false ? 'checked' : ''}> extra luminaires at crossings</label>
      <label class="chk"><input type="checkbox" id="lJ" ${lo.junction_poles !== false ? 'checked' : ''}> a pole at each junction</label>
    </div>
    <button class="btn big" id="btnRoute" style="margin-top:12px" ${R.sel ? '' : 'disabled'}>Lay out and check the whole route</button>
    ${rr ? routeSummary(rr) : ''}
    ${nav('results', rr ? 'elec' : null, 'Next: cables and supply')}`;
  bindNav();
  $('#btnRoute').onclick = async () => {
    Object.assign(lo, { margin: fval('lM', 0.95), crest_factor: fval('lC', 0.85), max_iter: fval('lI', 6), tree_clearance: fval('lT', 1),
      curve_rule: $('#lB').checked, outside_on_bends: $('#lO').checked, extra_crossing: $('#lX').checked, junction_poles: $('#lJ').checked });
    save();
    const r = await run('Placing poles along the route and checking every span…', () => api('/route', { project: P, candidate: R.sel }));
    if (!r) return;
    R.route = r; delete R.elec; delete R.struct;
    pageLayout(); setView('3d'); refreshView();
    toast(r.ok ? 'The whole route complies.' : 'Some checks need attention — see the list.', r.ok ? 'ok' : 'info');
  };
  if (rr) {
    $('#csvPoles').onclick = () => {
      const L = ['id,chainage_m,x_m,y_m,z_ground_m,height_m,arm_m,tilt_deg,side,luminaire,output,reason'];
      for (const p of rr.poles) L.push([p.id, p.s.toFixed(2), p.x.toFixed(3), p.yw.toFixed(3), p.z0.toFixed(3), p.H, p.overhang, p.tilt, p.side > 0 ? 'A' : 'B', P.luminaires[p.phot]?.name || p.phot, (p.flux * 100).toFixed(0) + '%', '"' + p.reason + '"'].join(','));
      download('poles.csv', L.join('\n'), 'text/csv');
    };
    $('#dxfRoute').onclick = () => exportRouteDXF();
  }
}
async function exportRouteDXF() {
  const r = await run('Writing the layout drawing…', () => api('/export/dxf_route', { project: P, poles: R.route.poles, result: R.route.result,
    electrical: R.elec || null, quantity: 'E', info: [P.name || '', R.sel.label + ', H ' + R.sel.H + ' m', 'Street Lighting ' + META.version] }));
  if (r) download(r.filename, r.text, 'application/dxf');
}

function routeSummary(rr) {
  const res = rr.result;
  return `
    <h3>Result ${verdict(rr.ok, 'the route complies', 'needs attention')}</h3>
    <div class="kpis">
      <div class="kpi"><b>${fmt(res.length, 0)} m</b><span>route length</span></div>
      <div class="kpi"><b>${res.n_poles}</b><span>columns</span></div>
      <div class="kpi"><b>${res.n_luminaires}</b><span>luminaires</span></div>
    </div>
    ${topoHTML(rr.topology)}
    ${(rr.adjustments || []).map(a => `<div class="box acc small">${esc(a)}</div>`).join('')}
    ${rr.checks.map(k => `<div class="crit"><span>${esc(k.area)} — ${esc(k.name)}</span><span class="v">${typeof k.value === 'number' && k.value % 1 ? fmt(k.value, 1) : k.value}</span><span class="rq">${k.name.startsWith('Threshold') ? '≤ ' + k.req + ' %' : 'of ' + k.req}</span>
      <span class="verdict ${k.ok ? 'ok' : 'bad'}">${k.ok ? 'pass' : 'fail'}</span><span class="why">${esc(k.reason)}</span></div>`).join('')}
    ${rr.history.length > 1 ? `<h4>Refinement</h4><table class="t small"><tr><th>Round</th><th class="n">Luminaires</th><th class="n">Failing spans</th></tr>${rr.history.map(h => `<tr><td>${esc(String(h.iteration))}</td><td class="n">${h.n_poles}</td><td class="n">${h.n_fail}</td></tr>`).join('')}</table>` : ''}
    ${res.areas.map(a => a.n_fail ? `<h4>${esc(a.name)}: spans that fail</h4><table class="t small"><tr><th>Chainage</th><th>Failing</th><th>Likely cause</th></tr>
      ${a.spans.filter(s => !s.ok).map(s => `<tr><td>${fmt(s.s0, 0)}–${fmt(s.s1, 0)}</td><td>${s.checks.filter(c => !c.ok).map(c => `${c.symbol} ${fmt(c.value, 2)} / ${fmt(c.req, 2)}`).join(', ')}</td><td>${(s.why || []).join(', ') || 'spacing'}</td></tr>`).join('')}</table>` : '').join('')}
    <h4>Columns that are not on the regular spacing</h4>
    <table class="t small"><tr><th>Id</th><th class="n">Ch</th><th class="n">H</th><th>Why</th></tr>
      ${rr.poles.filter(p => p.reason !== 'regular spacing').slice(0, 40).map(p => `<tr><td>${p.id}</td><td class="n">${fmt(p.s, 1)}</td><td class="n">${fmt(p.H, 1)}</td><td>${esc(p.reason)}</td></tr>`).join('') || '<tr><td colspan="4">none</td></tr>'}</table>
    <div class="row" style="margin-top:10px"><button class="btn2" id="dxfRoute">Layout drawing (DXF)</button><button class="btn2" id="csvPoles">Column schedule (CSV)</button></div>`;
}

// ---------------------------------------------------------------------------
// step 7 — electrical
// ---------------------------------------------------------------------------
function pageElec() {
  const c = P.electrical || (P.electrical = {});
  const d = META.electrical_defaults;
  const g = k => c[k] ?? d[k];
  $('#panel').innerHTML = `
    <h2>Electrical</h2>
    <p class="lead">Feeder pillars, circuits and cables: each pillar position and every cable size is tried, and the
    cheapest arrangement that meets current capacity, voltage drop, fault disconnection and short-circuit withstand is kept.</p>
    ${R.route ? '' : need('Lay the poles out along the route first (step 6).', 'layout', 'Go to step 6')}
    <div class="grid2">
      ${field('Earthing system', sel('eSys', ['TN-S', 'TN-C-S', 'TT'], g('system')))}
      ${field('Phase voltage U<sub>0</sub>', num('eU', g('U0'), 1), 'V')}
      ${field('Conductor', sel('eMat', [['Cu', 'Copper'], ['Al', 'Aluminium']], g('material')))}
      ${field('Insulation', sel('eIns', [['XLPE', 'XLPE / EPR (90 °C)'], ['PVC', 'PVC (70 °C)']], g('insulation')))}
      ${field('Installation', sel('eMeth', [['D2', 'Direct in ground (D2)'], ['D1', 'In buried duct (D1)']], g('method')))}
      ${field('Protective device', sel('eDev', [['B', 'MCB type B'], ['C', 'MCB type C'], ['D', 'MCB type D'], ['gG', 'Fuse gG']], g('device')))}
      ${field('gG fuse: I<sub>a</sub> / I<sub>n</sub> at 0.4 s', num('eGk', c.gg_k04 ?? '', 0.1, 'placeholder="IEC 60269 gate"'), 'from the fuse curve')}
      ${field('Max voltage drop', num('eDu', g('du_max'), 0.5), '%')}
      ${field('Power factor', num('ePf', g('pf'), 0.01))}
      ${field('Ground temperature', num('eTg', g('t_ground'), 1), '°C')}
      ${field('Soil thermal resistivity', num('eRs', g('rho_soil'), 0.1), 'K·m/W')}
      ${field('Supply loop impedance Z<sub>e</sub>', num('eZe', g('Ze'), 0.01), 'Ω')}
      ${field('Fault current at the pillar', num('eIk', g('Ik_pillar'), 100), 'A')}
      ${field('Earth electrode R<sub>A</sub> (TT)', num('eRa', g('RA'), 1), 'Ω')}
      ${field('RCD IΔn (TT)', num('eIdn', g('Idn'), 0.01), 'A')}
      ${field('Drivers per B16 breaker', num('eDrv', g('max_drivers_B16'), 1), 'inrush')}
      ${field('Pillar cost', num('ePc', g('pillar_cost'), 10))}
    </div>
    <button class="btn big" id="btnElec" style="margin-top:12px" ${R.route ? '' : 'disabled'}>Design the supply</button>
    <div id="elecOut">${R.elec ? elecHTML(R.elec) : ''}</div>
    ${nav('layout', 'struct', 'Next: columns')}`;
  bindNav();
  $('#btnElec').onclick = async () => {
    Object.assign(c, { system: val('eSys'), U0: fval('eU', 230), material: val('eMat'), insulation: val('eIns'), method: val('eMeth'),
      device: val('eDev'), du_max: fval('eDu', 3), pf: fval('ePf', 0.95), t_ground: fval('eTg', 25), rho_soil: fval('eRs', 2.5),
      Ze: fval('eZe', 0.35), Ik_pillar: fval('eIk', 6000), RA: fval('eRa', 30), Idn: fval('eIdn', 0.3), max_drivers_B16: fval('eDrv', 20),
      pillar_cost: fval('ePc', 1800), gg_k04: val('eGk') ? fval('eGk') : null });
    save();
    const r = await run('Sizing cables and placing feeder pillars…', () => api('/electrical', { project: P, poles: R.route.poles }));
    if (!r) return;
    R.elec = r;
    $('#elecOut').innerHTML = elecHTML(r);
    setView('route');
  };
}
function elecHTML(e) {
  return `<h3>${e.n_pillars} feeder pillar${e.n_pillars > 1 ? 's' : ''} ${verdict(e.ok, 'all circuits pass', 'some circuits fail')}</h3>
    <p class="small">Connected load ${fmt(e.total_W / 1000, 2)} kW on ${e.n_poles} columns · cable and pillars about ${fmt(e.cost, 0)} ${(P.costs || {}).currency || ''}</p>
    <table class="t small"><tr><th>Feeder</th><th class="n">Lum.</th><th class="n">Cable</th><th class="n">Length</th><th class="n">I<sub>b</sub></th><th class="n">I<sub>n</sub></th><th class="n">I<sub>z</sub></th><th class="n">ΔU %</th><th class="n">Z<sub>s</sub> / max</th></tr>
    ${e.feeders.map(f => `<tr><td>${f.id}</td><td class="n">${f.poles.length}</td><td class="n">${f.size} mm²</td><td class="n">${fmt(f.length, 0)} m</td><td class="n">${fmt(f.Ib, 1)}</td><td class="n">${f.In}</td><td class="n">${fmt(f.Iz, 0)}</td><td class="n">${fmt(f.du_max, 2)}</td><td class="n">${fmt(f.Zs, 2)} / ${fmt(f.Zs_max, 2)}</td></tr>
      ${f.msgs.length ? `<tr><td colspan="9" class="note">${f.msgs.map(esc).join('; ')}</td></tr>` : ''}`).join('')}</table>
    <p class="note">Cable capacity from IEC 60364-5-52 Tables B.52.2–B.52.5 with correction factors; voltage drop by Annex G
    computed phase by phase for the distributed load (luminaires rotated L1-L2-L3); disconnection per IEC 60364-4-41
    (Z<sub>s</sub> ≤ 0.95 U<sub>0</sub> / I<sub>a</sub>, slightly stricter than Z<sub>s</sub> × I<sub>a</sub> ≤ U<sub>0</sub>).</p>
    ${(e.installation_notes || []).length ? `<details class="adv"><summary>Site requirements (IEC 60364-7-714)</summary>
      <ul class="small">${e.installation_notes.map(n => `<li>${esc(n)}</li>`).join('')}</ul></details>` : ''}`;
}

// ---------------------------------------------------------------------------
// step 8 — columns and foundations
// ---------------------------------------------------------------------------
function pageStruct() {
  const s = P.structural || (P.structural = { wind: {}, soil: {} });
  const w = s.wind || (s.wind = {}), so = s.soil || (s.soil = {});
  $('#panel').innerHTML = `
    <h2>Columns</h2>
    <p class="lead">Wind on the column, arm and luminaire (EN 40-3-1), the lightest tapered steel column that passes
    the EN 40-3-3 checks at the base and at the door opening, and the depth of the foundation (Broms and PD 6547).</p>
    <div class="grid2">
      ${field('Reference wind speed V<sub>ref</sub>', num('wV', w.Vref ?? 27, 0.5), 'm/s, 10-min mean, 50-yr')}
      ${field('Terrain category', sel('wT', Object.entries(META.terrain).map(([k, v]) => [k, k + ' — ' + v.label]), w.terrain || 'II'))}
      ${field('Steel grade', sel('wG', ['S235', 'S275', 'S355'], w.grade || 'S355'))}
      ${field('Load class', sel('wL', [['A', 'A (wind 1.4)'], ['B', 'B (wind 1.2)']], w.load_class || 'A'))}
      ${field('Deflection class', sel('wD', [[1, '1 (strict)'], [2, '2'], [3, '3']], w.defl_class || 2))}
      ${field('Soil', sel('soilT', [['cohesionless', 'Sand / gravel'], ['cohesive', 'Clay']], so.type || 'cohesionless'))}
      ${field('Friction angle φ (sand)', num('soilP', so.phi ?? 30, 1), '°')}
      ${field('Undrained strength c<sub>u</sub> (clay)', num('soilC', so.cu ?? 50, 5), 'kPa')}
      ${field('Foundation diameter', num('soilD', so.D ?? 0.6, 0.05), 'm')}
      ${field('Ground quality (PD 6547)', sel('soilQ', [['good', 'Good'], ['average', 'Average'], ['poor', 'Poor']], so.quality || 'average'))}
    </div>
    <button class="btn big" id="btnSt" style="margin-top:12px" ${R.sel ? '' : 'disabled'}>Size the columns</button>
    <div id="stOut">${R.struct ? structHTML(R.struct) : ''}</div>
    ${nav('elec', 'energy', 'Next: energy and cost')}`;
  bindNav();
  $('#btnSt').onclick = async () => {
    Object.assign(w, { Vref: fval('wV', 27), terrain: val('wT'), grade: val('wG'), defl_class: +val('wD'), load_class: val('wL') });
    Object.assign(so, { type: val('soilT'), phi: fval('soilP', 30), cu: fval('soilC', 50), D: fval('soilD', 0.6), quality: val('soilQ') });
    save();
    const kinds = new Map();
    const poles = R.route ? R.route.poles : R.sel.rows.map(r => ({ H: r.height, overhang: r.overhang, phot: r.phot, s: 0, y: r.y }));
    const heads = new Map();
    for (const p of poles) { const k = `${p.s.toFixed(2)}|${p.y.toFixed(2)}`; heads.set(k, (heads.get(k) || 0) + 1); }
    for (const p of poles) {
      const n = heads.get(`${p.s.toFixed(2)}|${p.y.toFixed(2)}`) > 1 ? 2 : 1;
      const key = `${p.H}|${p.overhang}|${n}|${p.phot}`;
      kinds.set(key, { H: p.H, overhang: p.overhang, n_heads: n, phot: p.phot, count: (kinds.get(key)?.count || 0) + 1 });
    }
    const out = [];
    for (const k of kinds.values()) {
      const r = await run('Checking the column…', () => api('/structural', { project: P, H: k.H, overhang: k.overhang, n_heads: k.n_heads, phot: k.phot }));
      if (r) out.push({ ...k, r });
    }
    R.struct = out;
    $('#stOut').innerHTML = structHTML(out);
    setView('diagram');
  };
}
function structHTML(list) {
  return `<table class="t small" style="margin-top:12px"><tr><th>Column</th><th class="n">No.</th><th class="n">Base Ø×t</th><th class="n">Use</th><th class="n">Deflection</th><th class="n">Foundation</th></tr>
    ${list.map(k => { const c = k.r.column, f = k.r.foundation;
      return `<tr><td>H ${fmt(k.H, 1)} m, arm ${fmt(k.overhang, 1)} m${k.n_heads > 1 ? ', twin' : ''}</td><td class="n">${k.count}</td>
      <td class="n">${fmt(c.D_base * 1000, 0)}×${fmt(c.t * 1000, 0)} mm</td><td class="n" title="base ${fmt(c.util_base * 100, 0)} %, door ${fmt(c.util_door * 100, 0)} %">${fmt(c.util * 100, 0)} %</td>
      <td class="n">${fmt(c.deflection * 1000, 0)} / ${fmt(c.defl_limit * 1000, 0)} mm</td><td class="n">Ø${fmt(f.diameter, 2)} × ${fmt(f.depth, 2)} m</td></tr>`; }).join('')}</table>
    <p class="note">"Use" is the larger EN 40-3-3 interaction ratio at the base and at the lower edge of an unreinforced
    door (500 × 120 mm, 0.6 m above ground); details are in the report. This is a pre-design; the column supplier's
    EN 40-3-3 verification governs.</p>`;
}

// ---------------------------------------------------------------------------
// step 9 — energy and cost
// ---------------------------------------------------------------------------
function pageEnergy() {
  const en = P.energy || (P.energy = { kind: 'bipower', hours: 4100, reduce_from: 0.5, level: 0.5, price: 0.12, co2: 0.55 });
  $('#panel').innerHTML = `
    <h2>Energy and cost</h2>
    <p class="lead">Energy indicators of EN 13201-5 (PDI and AECI), yearly consumption, cost and CO₂ for the operating
    profile you choose.</p>
    <div class="grid2">
      ${field('Operating profile', sel('nK', [['full', 'Full output all night'], ['bipower', 'Dimmed after midnight'], ['tripower', 'Three levels']], en.kind))}
      ${field('Burning hours / year', num('nH', en.hours, 50), 'h')}
      ${field('Share of the night dimmed', num('nR', en.reduce_from, 0.05), '0–1')}
      ${field('Dimmed level', num('nL', en.level, 0.05), '× full')}
      ${field('Energy price', num('nP', en.price, 0.01), 'per kWh')}
      ${field('Grid emission factor', num('nC', en.co2, 0.01), 'kg CO₂/kWh')}
      ${field('Standby power per luminaire', num('nS', en.standby_W ?? 0.5, 0.1), 'W')}
      ${field('Years', num('nY', en.years ?? 20, 1))}
    </div>
    <div class="row end" style="margin-top:8px"><button class="btn2" id="btnEn">Update</button></div>
    <div id="enOut">${energyHTML()}</div>
    ${nav('struct', 'report', 'Next: report')}`;
  bindNav();
  $('#btnEn').onclick = () => {
    Object.assign(en, { kind: val('nK'), hours: fval('nH', 4100), reduce_from: fval('nR', 0.5), level: fval('nL', 0.5), price: fval('nP', 0.12),
      co2: fval('nC', 0.55), standby_W: fval('nS', 0.5), years: fval('nY', 20) });
    save();
    $('#enOut').innerHTML = energyHTML();
    refreshView();
  };
}
function profileOf(en) {
  const h = en.hours || 4100;
  if (en.kind === 'bipower') return [[1, h * (1 - en.reduce_from)], [en.level, h * en.reduce_from]];
  if (en.kind === 'tripower') return [[1, h * 0.35], [0.7, h * 0.25], [en.level, h * 0.4]];
  return [[1, h]];
}
export function energyFigures() {
  const en = P.energy || {};
  let W, area, EA, n;
  if (R.route) {
    const res = R.route.result;
    W = R.route.poles.reduce((a, p) => a + (LUM[p.phot]?.power || 0) * (0.08 + 0.92 * (p.flux || 1)), 0);
    area = res.areas.reduce((a, x) => a + (x.y1 - x.y0) * res.length, 0);
    EA = res.areas.reduce((a, x) => a + x.E_avg * (x.y1 - x.y0) * res.length, 0);
    n = R.route.poles.length;
  } else if (R.eval) {
    const c = R.sel;
    W = c.rows.length * (LUM[c.phot]?.power || 0) * (0.08 + 0.92 * c.f);
    area = R.eval.areas.filter(a => a.cls).reduce((a, x) => a + x.width * c.S, 0);
    EA = R.eval.areas.filter(a => a.cls).reduce((a, x) => a + x.E_avg * x.width * c.S, 0);
    n = c.rows.length;
  } else return null;
  const prof = profileOf(en);
  const on = prof.reduce((a, p) => a + p[1], 0);
  const Wh = prof.reduce((a, p) => a + W * p[0] * p[1], 0) + (en.standby_W ?? 0.5) * n * Math.max(8760 - on, 0);
  const full = W * on;
  const yrs = en.years ?? 20;
  return { W, area, PDI: W / EA, AECI: Wh / area, kWh: Wh / 1000, fullkWh: full / 1000, cost: Wh / 1000 * en.price,
    co2: Wh / 1000 * en.co2 / 1000, life: Wh / 1000 * en.price * yrs, n, scope: R.route ? 'the whole route' : 'one span (representative section)' };
}
function energyHTML() {
  const f = energyFigures();
  if (!f) return need('Run the design search first; the energy figures follow from it.', 'design', 'Go to step 4');
  const cur = (P.costs || {}).currency || '';
  return `<div class="kpis">
      <div class="kpi"><b>${fmt(f.PDI * 1000, 1)}</b><span>PDI D<sub>P</sub> mW/(lx·m²)</span></div>
      <div class="kpi"><b>${fmt(f.AECI / 1000, 2)}</b><span>AECI D<sub>E</sub> kWh/(m²·yr)</span></div>
      <div class="kpi"><b>${fmt(f.W / 1000, 2)} kW</b><span>installed (at design output)</span></div>
      <div class="kpi"><b>${fmt(f.kWh, 0)}</b><span>kWh per year</span></div>
      <div class="kpi"><b>${fmt(f.cost, 0)} ${esc(cur)}</b><span>energy per year</span></div>
      <div class="kpi"><b>${fmt(f.co2, 2)} t</b><span>CO₂ per year</span></div></div>
    <p class="note">For ${f.scope}. Dimming saves ${fmt(100 * (1 - f.kWh / Math.max(f.fullkWh, 1e-9)), 0)} % against full output all night.</p>`;
}

// ---------------------------------------------------------------------------
// step 10 — report and export
// ---------------------------------------------------------------------------
function pageReport() {
  $('#panel').innerHTML = `
    <h2>Report</h2>
    <p class="lead">A complete design report with drawings, isolux and isoluminance contours, the reason for every
    pass or fail, the cable and column schedules and the energy figures. Print it or save it as PDF from the report window.</p>
    ${field('Language', sel('repLang', [['en', 'English'], ['fa', 'فارسی (Persian)'], ['both', 'English + فارسی']], P.report_lang || 'en'))}
    <div class="grid2" style="margin-top:8px">
      ${field('Prepared by', `<input type="text" id="repBy" value="${esc(P.report_by || '')}">`)}
      ${field('Client', `<input type="text" id="repFor" value="${esc(P.report_for || '')}">`)}
    </div>
    <button class="btn big" id="btnRep" style="margin-top:12px" ${R.eval ? '' : 'disabled'}>Open the report</button>
    <h3>Files</h3>
    <div class="row">
      <button class="btn2" id="xRoute" ${R.route ? '' : 'disabled'}>Route layout (DXF)</button>
      <button class="btn2" id="xSec" ${R.eval ? '' : 'disabled'}>Typical section (DXF)</button>
      <button class="btn2" id="xLdt">Luminaire (LDT)</button>
      <button class="btn2" id="xJson">Project (JSON)</button>
    </div>
    <p class="note">DXF files open in AutoCAD, BricsCAD, LibreCAD and QCAD (metres, layers for road, poles, cables and isolines).</p>
    ${nav('energy', null)}`;
  bindNav();
  const keep = () => { P.report_lang = val('repLang'); P.report_by = val('repBy'); P.report_for = val('repFor'); save(); };
  $('#btnRep').onclick = async () => {
    keep();
    const imgs = {};
    try {
      setView('3d');
      const old = viewMode;
      if (old !== 'night') v3.setMode('night', 'L');
      v3.view('bird'); imgs.night = v3.snapshot();
      v3.view('driver'); imgs.day = v3.snapshot();
      v3.view('bird');
      if (old !== 'night') v3.setMode(old, viewQty);
    } catch (e) { /* no WebGL */ }
    openReport({ P, R, LUM, META, imgs, energy: energyFigures(), lang: P.report_lang || 'en' });
  };
  $('#xRoute').onclick = exportRouteDXF;
  $('#xSec').onclick = async () => {
    const r = await run('Writing the drawing…', () => api('/export/dxf_section', { project: P, candidate: R.sel, result: R.eval, info: [P.name || ''] }));
    if (r) download(r.filename, r.text, 'application/dxf');
  };
  $('#xLdt').onclick = async () => {
    const k = R.sel ? R.sel.phot : Object.keys(P.luminaires)[0];
    if (!k) return;
    const r = await run('Writing EULUMDAT…', () => api('/export/ldt', { spec: P.luminaires[k] }));
    if (r) download(r.filename, r.text);
  };
  $('#xJson').onclick = () => download((P.name || 'project').replace(/\s+/g, '_') + '.json', JSON.stringify(P, null, 1), 'application/json');
}

// ---------------------------------------------------------------------------
// viewer
// ---------------------------------------------------------------------------
function refreshView() {
  if (!META) return;
  if (view === '3d') return refresh3D();
  if (view === 'xsec') return refreshXsec();
  if (view === 'plan') return refreshPlan();
  if (view === 'route') return refreshRoute();
  if (view === 'profile') return refreshProfile();
  if (view === 'diagram') return refreshDiagrams();
}

function previewRows() {
  if (R.sel) return R.sel.rows;
  const el = elements();
  const edges = edgesOf(el);
  const ci = el.findIndex(e => e.kind === 'carriageway');
  const y = ci >= 0 ? Math.max(edges[ci][0] - 0.8, 0) : 0.5;
  const W = el.reduce((a, e) => a + (+e.width || 0), 0);
  return [{ y, side: 1, overhang: 1, height: W > 12 ? 12 : W > 8 ? 10 : 8, tilt: 5, phase: 0 }];
}

function refreshXsec() {
  const trees = ((P.route.features || {}).tree_lines || []).filter(t => t.y !== undefined);
  const rows = previewRows();
  let h = `<h3>Cross-section ${R.sel ? '— selected design' : '— preview'}</h3><div class="card">${D.crossSection(elements(), rows, { trees, selected: selStrip })}</div>`;
  if (!R.sel) h += '<p class="note">The column shown is only a preview; the design search chooses the height, arm, tilt and spacing.</p>';
  $('#vxsec').innerHTML = h;
}

function refreshPlan() {
  if (!R.eval) { $('#vplan').innerHTML = '<h3>Contours</h3><p>Run the design search to see isolux and isoluminance contours.</p>'; return; }
  const q = viewQty;
  const out = D.sectionPlan(P.section, R.sel, R.eval, { quantity: q, scale: colourScale, points: true, map: viewMode !== 'day' });
  const out2 = D.sectionPlan(P.section, R.sel, R.eval, { quantity: q === 'L' ? 'E' : 'L', scale: colourScale, map: viewMode !== 'day' });
  $('#vplan').innerHTML = `<h3>${q === 'L' ? 'Isoluminance (cd/m²)' : 'Isolux (lx)'} — two spans</h3>
    <div class="card">${out.svg}<div class="legendrow">${legendSVG(out.vmax, out.unit, colourScale, out.levels.filter((_, i) => i % 2 === 0), 320)}
    <span class="small">Dots are the EN 13201-3 calculation points. ${q === 'L' ? 'Luminance as seen by the observer in lane 1, 60 m before the field.' : ''}</span></div></div>
    <h3>${q === 'L' ? 'Isolux (lx)' : 'Isoluminance (cd/m²)'}</h3><div class="card">${out2.svg}<div class="legendrow">${legendSVG(out2.vmax, out2.unit, colourScale, [], 320)}</div></div>
    <p class="note">Scroll on a drawing to zoom, drag to move, double-click to reset.</p>`;
  $$('#vplan svg.plan').forEach(panZoom);
}

let dragIdx = -1;
function refreshRoute() {
  const host = $('#vroute');
  if (R.route) {
    const q = viewQty;
    const out = D.routePlan(R.route, { quantity: q, scale: colourScale, electrical: R.elec, ids: true, map: viewMode !== 'day' });
    host.innerHTML = `<h3>Route — ${q === 'L' ? 'isoluminance (cd/m²)' : 'isolux (lx)'}${R.elec ? ' with cables' : ''}</h3>
      <div class="card">${out.svg}<div class="legendrow">${legendSVG(out.vmax, out.unit, colourScale, [], 320)}
      ${R.elec ? '<span class="small">Dashed lines: feeder cables; dark squares: feeder pillars.</span>' : ''}</div></div>
      ${R.route.result.areas.map(a => {
        const k = a.L_avg !== undefined ? 'L_avg' : 'E_avg';
        const req = a.spans[0]?.checks?.[0]?.req;
        return `<h3>${esc(a.name)} — ${k === 'L_avg' ? 'average luminance' : 'average illuminance'} per span</h3><div class="card" data-spans="${esc(a.name)}"></div>`;
      }).join('')}`;
    panZoom(host.querySelector('svg.plan'));
    R.route.result.areas.forEach((a, i) => {
      const k = a.L_avg !== undefined ? 'L_avg' : 'E_avg';
      C.spansChart(host.querySelectorAll('[data-spans]')[i], a, k, a.spans[0]?.checks?.[0]?.req, k === 'L_avg' ? 'cd/m²' : 'lx');
    });
    return;
  }
  // geometry preview / drawing pad
  const r = P.route;
  const pts = r.points || [];
  const g = R.geom;
  const W = 1000, H = 640;
  let xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
  if (g) { xs = xs.concat(g.alignment.x); ys = ys.concat(g.alignment.y); }
  if (!xs.length) { xs = [0, 400]; ys = [-150, 150]; }
  let x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const span = Math.max(x1 - x0, y1 - y0, 200) * 1.25;
  const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
  const vb = r._vb || [cx - span / 2, cy - span / 2 * H / W, span, span * H / W];
  if (r.mode === 'points' && !r._vb) r._vb = [...vb];          // keep the view still while drawing
  const sc = W / vb[2];
  const X = x => (x - vb[0]) * sc, Y = y => (vb[1] + vb[3] - y) * sc;
  let svg = `<svg id="pad" class="drawpad" viewBox="0 0 ${W} ${H}" width="100%">`;
  const grid = +(r.grid || 25);
  for (let gx = Math.floor(vb[0] / grid) * grid; gx < vb[0] + vb[2]; gx += grid) svg += `<line x1="${X(gx)}" y1="0" x2="${X(gx)}" y2="${H}" stroke="${gx % (grid * 4) ? '#eef1f3' : '#dde3e7'}"/>`;
  for (let gy = Math.floor(vb[1] / grid) * grid; gy < vb[1] + vb[3]; gy += grid) svg += `<line x1="0" y1="${Y(gy)}" x2="${W}" y2="${Y(gy)}" stroke="${gy % (grid * 4) ? '#eef1f3' : '#dde3e7'}"/>`;
  if (g) {
    const al = g.alignment;
    const off = (t) => al.x.map((x, i) => [x - Math.sin(al.h[i]) * t, al.y[i] + Math.cos(al.h[i]) * t]);
    const Wd = g.width, ry = g.ref_y;
    let yy = 0;
    const el = elements();
    el.forEach((e, k) => {
      const a = off(yy - ry), b = off(yy + (+e.width) - ry);
      const poly = a.concat(b.reverse());
      svg += `<path d="${poly.map((p, i) => (i ? 'L' : 'M') + X(p[0]).toFixed(1) + ' ' + Y(p[1]).toFixed(1)).join('')}Z" fill="${D.stripColour(e.kind)}" stroke="#fff" stroke-width="0.6"/>`;
      yy += +e.width;
    });
    svg += `<path d="${al.x.map((x, i) => (i ? 'L' : 'M') + X(x).toFixed(1) + ' ' + Y(al.y[i]).toFixed(1)).join('')}" fill="none" stroke="#c8412c" stroke-width="1" stroke-dasharray="8 4"/>`;
    for (let i = 0; i < al.s.length; i++) if (Math.abs(al.s[i] % 50) < 0.51 || Math.abs(al.s[i] % 50 - 50) < 0.51) {
      svg += `<circle cx="${X(al.x[i])}" cy="${Y(al.y[i])}" r="2.5" fill="#17212b"/><text x="${X(al.x[i]) + 5}" y="${Y(al.y[i]) - 5}" font-size="10" fill="#17212b">${Math.round(al.s[i])}</text>`;
    }
    for (const t of g.trees || []) svg += `<circle cx="${X(t.x)}" cy="${Y(t.y)}" r="${Math.max(t.r * sc, 1.5)}" fill="#3f7a3a" fill-opacity="0.6"/>`;
    const at = (s) => { const i = al.s.findIndex(v => v >= s); return i < 0 ? al.s.length - 1 : i; };
    for (const c of (r.features.crossings || [])) { const i = at(c.s); svg += `<circle cx="${X(al.x[i])}" cy="${Y(al.y[i])}" r="6" fill="none" stroke="#f2c230" stroke-width="3"/>`; }
    for (const j of (r.features.junctions || [])) { const i = at(j.s); svg += `<rect x="${X(al.x[i]) - 6}" y="${Y(al.y[i]) - 6}" width="12" height="12" fill="none" stroke="#1f5f9e" stroke-width="2.5"/>`; }
  }
  if (r.mode === 'points') {
    svg += `<path d="${pts.map((p, i) => (i ? 'L' : 'M') + X(p[0]).toFixed(1) + ' ' + Y(p[1]).toFixed(1)).join('')}" fill="none" stroke="#1f5f9e" stroke-width="1.2"/>`;
    pts.forEach((p, i) => { svg += `<circle data-pt="${i}" cx="${X(p[0])}" cy="${Y(p[1])}" r="6" fill="#f2c230" stroke="#17212b" stroke-width="1.2" style="cursor:move"/>`; });
  }
  svg += '</svg>';
  host.innerHTML = `<h3>Route plan ${r.mode === 'points' ? (drawing ? '— click to add points' : '— drag points to edit') : ''}</h3>
    <div class="card">${svg}<p class="small">Scroll to zoom, drag with the middle button or Shift to pan. ${g ? `Length ${fmt(g.length, 1)} m.` : ''}
    Strips are drawn to scale; the dashed red line is the reference line.</p></div>`;
  wirePad(vb, W, H);
}

function wirePad(vb, W, H) {
  const pad = $('#pad');
  if (!pad) return;
  const r = P.route;
  const toWorld = (ev) => {
    const b = pad.getBoundingClientRect();
    const px = (ev.clientX - b.left) / b.width * W, py = (ev.clientY - b.top) / b.height * H;
    return [vb[0] + px / W * vb[2], vb[1] + vb[3] - py / H * vb[3]];
  };
  const snap = (p) => { const g = 0.5; return [Math.round(p[0] / g) * g, Math.round(p[1] / g) * g]; };
  let pan = null;
  pad.onwheel = (ev) => {
    ev.preventDefault();
    const p = toWorld(ev);
    const f = ev.deltaY > 0 ? 1.15 : 1 / 1.15;
    r._vb = [p[0] - (p[0] - vb[0]) * f, p[1] - (p[1] - vb[1]) * f, vb[2] * f, vb[3] * f];
    refreshRoute();
  };
  pad.onpointerdown = (ev) => {
    const t = ev.target.closest('[data-pt]');
    if (ev.button === 1 || ev.shiftKey) { pan = { p: toWorld(ev), vb: [...vb] }; pad.setPointerCapture(ev.pointerId); return; }
    if (r.mode !== 'points') return;
    if (t && ev.button === 2) { r.points.splice(+t.dataset.pt, 1); geomChanged(); refreshRoute(); return; }
    if (t) { dragIdx = +t.dataset.pt; pad.setPointerCapture(ev.pointerId); return; }
    if (drawing && ev.button === 0) { (r.points || (r.points = [])).push(snap(toWorld(ev))); geomChanged(); refreshRoute(); }
  };
  pad.oncontextmenu = ev => ev.preventDefault();
  pad.onpointermove = (ev) => {
    if (pan) {
      const p = toWorld(ev);
      r._vb = [pan.vb[0] - (p[0] - pan.p[0]), pan.vb[1] - (p[1] - pan.p[1]), pan.vb[2], pan.vb[3]];
      vb.splice(0, 4, ...r._vb);
      refreshRoute();
      return;
    }
    if (dragIdx >= 0) {
      r.points[dragIdx] = snap(toWorld(ev));
      const c = pad.querySelector(`[data-pt="${dragIdx}"]`);
      const sc = W / vb[2];
      if (c) { c.setAttribute('cx', (r.points[dragIdx][0] - vb[0]) * sc); c.setAttribute('cy', (vb[1] + vb[3] - r.points[dragIdx][1]) * sc); }
    }
  };
  pad.onpointerup = () => { if (dragIdx >= 0) { dragIdx = -1; geomChanged(); refreshRoute(); } pan = null; };
}

function refreshProfile() {
  const host = $('#vprofile');
  if (R.route) {
    host.innerHTML = `<h3>Vertical profile with columns</h3><div class="card" id="profChart"></div>
      <p class="note">Hover the road for chainage, level and grade; hover or Tab to a column to see why it stands there.</p>`;
    C.profileChart($('#profChart'), { ...R.route, poles: R.route.poles });
    return;
  }
  if (R.geom) {
    host.innerHTML = `<h3>Vertical profile</h3><div class="card" id="profChart"></div><p class="note">Hover the road for chainage, level and grade. Columns appear after the layout step.</p>`;
    C.profileChart($('#profChart'), { alignment: R.geom.alignment, profile: R.geom.profile, poles: [] });
    return;
  }
  host.innerHTML = '<h3>Vertical profile</h3><p>Enter the route in step 3 and press "Read the topology".</p>';
}

function refreshDiagrams() {
  let h = '';
  const keys = Object.keys(P.luminaires || {});
  if (keys.length) {
    h += '<h3>Luminaires — light distribution</h3><div class="row" style="align-items:flex-start;gap:14px">';
    for (const k of keys) {
      const i = LUM[k];
      if (!i) continue;
      h += `<div class="card" style="width:340px"><b>${esc(P.luminaires[k].name || i.name)}</b>${D.polarSVG(i.polar, 310)}
        <table class="t small"><tr><td>Lamp / luminaire flux</td><td class="n">${fmt(i.lamp_flux, 0)} / ${fmt(i.luminaire_flux, 0)} lm</td></tr>
        <tr><td>Power · efficacy</td><td class="n">${fmt(i.power, 1)} W · ${fmt(i.efficacy, 0)} lm/W</td></tr>
        <tr><td>LOR · ULOR</td><td class="n">${fmt(i.lor * 100, 1)} % · ${fmt(i.ulor * 100, 2)} %</td></tr>
        <tr><td>Peak intensity</td><td class="n">${fmt(i.imax, 0)} cd at C${fmt(i.imax_C, 0)} γ${fmt(i.imax_gamma, 0)}</td></tr>
        <tr><td>Intensity class (no tilt)</td><td class="n">${i.gstar.cls}</td></tr><tr><td>Glare index class</td><td class="n">${i.glare.cls}</td></tr>
        <tr><td>Street side</td><td class="n">${i.street_side > 0 ? 'C90' : 'C270 (turned automatically)'}</td></tr></table>
        ${i.notes && i.notes.length ? `<p class="note">${i.notes.map(esc).join(' ')}</p>` : ''}</div>`;
    }
    h += '</div>';
  }
  if (R.elec) h += `<h3>Single-line diagram</h3><div class="card">${D.sldSVG(R.elec)}</div>`;
  if (R.struct && R.struct.length) {
    h += '<h3>Columns and foundations</h3><div class="row" style="align-items:flex-start">';
    for (const k of R.struct) {
      const c = k.r.column;
      h += `<div class="card" style="width:330px">${D.columnSVG(k.r, k.H, k.overhang)}<table class="t small">
        <tr><td>q(10) · q(h)</td><td class="n">${fmt(c.q10, 0)} · ${fmt(c.q_h, 0)} Pa</td></tr>
        <tr><td>Natural period · β</td><td class="n">${fmt(c.T, 2)} s · ${fmt(c.beta, 2)}</td></tr>
        <tr><td>Base moment (wind + dead)</td><td class="n">${fmt((c.M_wind + c.M_dead) / 1000, 2)} kNm</td></tr>
        <tr><td>Design stress / f<sub>y</sub>/γ<sub>M</sub></td><td class="n">${fmt(c.sigma, 0)} / ${fmt(c.fy / 1.1, 0)} MPa</td></tr>
        <tr><td>Foundation</td><td class="n">${esc(k.r.foundation.method)}</td></tr></table></div>`;
    }
    h += '</div>';
  }
  const f = energyFigures();
  if (f) {
    const en = P.energy || {};
    const prof = profileOf(en);
    h += `<h3>Operating profile</h3><div class="card">${D.bars(prof.map(([lv, hr]) => ({ label: fmt(lv * 100, 0) + ' % output', v: hr })), 'h/yr')}</div>`;
  }
  $('#vdiagram').innerHTML = h || '<h3>Diagrams</h3><p>Add a luminaire to see its light distribution.</p>';
}

// --------------------------- 3D scene assembly -----------------------------
function interpGrid(xs, ys, Z, x, y) {
  const fi = (arr, v) => { let i = 0; while (i < arr.length - 2 && arr[i + 1] < v) i++; return [i, clamp((v - arr[i]) / ((arr[i + 1] - arr[i]) || 1), 0, 1)]; };
  const [i, u] = fi(xs, x), [j, t] = fi(ys, y);
  const a = Z[j][i], b = Z[j][i + 1], c = Z[j + 1][i + 1], d = Z[j + 1][i];
  return (1 - u) * (1 - t) * a + u * (1 - t) * b + u * t * c + (1 - u) * t * d;
}

function sectionScene() {
  const el = elements();
  const edges = edgesOf(el);
  const rows = previewRows();
  const S = R.sel ? R.sel.S : 30;
  const disp = R.eval ? R.eval.display : null;
  const x0 = disp ? disp.x[0] : -S * 0.5, x1 = disp ? disp.x[disp.x.length - 1] : S * 1.5;
  const nx = disp ? disp.x.length : 2;
  const xsS = disp ? disp.x : [x0, x1];
  const surfaces = [];
  let vmaxE = 0, vmaxL = 0;
  el.forEach((e, k) => {
    const [y0, y1] = edges[k];
    if (y1 - y0 <= 0) return;
    const ny = Math.max(2, Math.ceil((y1 - y0) / 0.4) + 1);
    const ys = Array.from({ length: ny }, (_, j) => y0 + (y1 - y0) * j / (ny - 1));
    const xyz = new Float32Array(nx * ny * 3), E = new Float32Array(nx * ny), L = e.kind === 'carriageway' && disp && disp.L ? new Float32Array(nx * ny) : null;
    for (let i = 0; i < nx; i++) for (let j = 0; j < ny; j++) {
      const kk = i * ny + j;
      xyz[3 * kk] = xsS[i]; xyz[3 * kk + 1] = ys[j]; xyz[3 * kk + 2] = 0;
      if (disp) {
        E[kk] = interpGrid(disp.x, disp.y, disp.E, xsS[i], ys[j]); vmaxE = Math.max(vmaxE, E[kk]);
        if (L) { L[kk] = interpGrid(disp.x, disp.y, disp.L, xsS[i], ys[j]); vmaxL = Math.max(vmaxL, L[kk]); }
      }
    }
    surfaces.push({ xyz, ns: nx, ny, E, L, kind: e.kind });
  });
  const poles = [];
  const labels = [], dims = [];
  for (const r of rows) {
    const side = r.side >= 0 ? 1 : -1;
    for (let k = -1; k <= 2; k++) {
      const x = (r.phase || 0) * S + k * S;
      if (x < x0 - 1e-6 || x > x1 + 1e-6) continue;
      poles.push({ base: [x, r.y, 0], head: [x, r.y + side * r.overhang, r.height], nu: side > 0 ? 0 : 180, tilt: r.tilt });
    }
  }
  if (rows.length) {
    const r = rows[0];
    labels.push({ p: [0, r.y - 1.2, r.height / 2], text: `H ${fmt(r.height, 1)} m` });
    labels.push({ p: [S / 2, r.y - 1.6, 0.4], text: `S ${fmt(S, 1)} m` });
    dims.push([[0, r.y - 1.0, 0.05], [S, r.y - 1.0, 0.05]]);
  }
  const marks = [];
  el.forEach((e, k) => {
    if (e.kind !== 'carriageway') return;
    const [y0, y1] = edges[k];
    const n = Math.max(1, e.lanes || 1);
    for (let j = 1; j < n; j++) {
      const y = y0 + (y1 - y0) * j / n;
      const line = [];
      for (let x = x0; x + 3 <= x1; x += 9) { line.push([x, y, 0], [x + 3, y, 0]); }
      marks.push(line);
    }
    marks.push([[x0, y0 + 0.2, 0], [x1, y0 + 0.2, 0]], [[x0, y1 - 0.2, 0], [x1, y1 - 0.2, 0]]);
  });
  const W = edges.length ? edges[edges.length - 1][1] : 10;
  const trees = [];
  const rlen = R.geom ? R.geom.length : routeLengthHint(P.route);
  const tl = (P.route.features || {}).tree_lines || [];
  const cover = tl.reduce((a, t) => a + Math.max(0, (t.s1 ?? rlen) - (t.s0 || 0)), 0);
  const useTrees = !rlen || cover / rlen >= 0.5;
  for (const t of useTrees ? tl : []) {
    const sp = t.spacing || 8;
    for (let x = Math.ceil(x0 / sp) * sp; x <= x1; x += sp) trees.push({ x, y: t.y, z0: 0, zc: ((+t.crown_base || 3) + (+t.height || 8)) / 2, r: +t.crown_radius || 2.5, rv: ((+t.height || 8) - (+t.crown_base || 3)) / 2 });
  }
  const cw = el.findIndex(e => e.kind === 'carriageway');
  const lane1 = cw >= 0 ? edges[cw][0] + (edges[cw][1] - edges[cw][0]) / (2 * (el[cw].lanes || 1)) : W / 2;
  return {
    surfaces, poles, trees, marks, labels, dims, vmax: { E: vmaxE || 1, L: vmaxL || 1 }, cct: R.sel ? (LUM[R.sel.phot]?.cct || 3000) : 3000,
    extent: { x0, x1, y0: 0, y1: W }, zmin: 0, start: null,
    driver: { eye: [x0 - 25, lane1, 1.5], look: [x1, lane1, 0.5] },
  };
}

function routeLengthHint(r) {
  if (r.mode === 'straight') return +r.length || 0;
  if (r.mode === 'segments') return (r.segments || []).reduce((a, g) => a + (g.type === 'arc' ? (+g.length || Math.abs(+g.angle || 0) * Math.PI / 180 * (+g.radius || 0)) : (+g.length || 0)), 0);
  const p = r.points || [];
  let L = 0;
  for (let i = 1; i < p.length; i++) L += Math.hypot(p[i][0] - p[i - 1][0], p[i][1] - p[i - 1][1]);
  return L;
}

function routeScene() {
  const rr = R.route;
  const surfaces = [];
  let vmaxE = 0, vmaxL = 0, zmin = Infinity;
  let ex = { x0: Infinity, x1: -Infinity, y0: Infinity, y1: -Infinity };
  for (const m of rr.result.display.meshes) {
    const xyz = Float32Array.from(m.xyz);
    for (let k = 0; k < xyz.length; k += 3) {
      ex.x0 = Math.min(ex.x0, xyz[k]); ex.x1 = Math.max(ex.x1, xyz[k]); ex.y0 = Math.min(ex.y0, xyz[k + 1]); ex.y1 = Math.max(ex.y1, xyz[k + 1]); zmin = Math.min(zmin, xyz[k + 2]);
    }
    for (const v of m.E) vmaxE = Math.max(vmaxE, v);
    if (m.L) for (const v of m.L) vmaxL = Math.max(vmaxL, v);
    surfaces.push({ xyz, ns: m.ns, ny: m.ny, E: m.E, L: m.L, kind: m.kind });
  }
  const poles = rr.result.luminaires.map(l => ({ base: l.pole, head: [l.x, l.y, l.z], nu: l.nu, tilt: l.tilt }));
  const trees = rr.result.trees.map(t => ({ x: t.x, y: t.y, zc: t.zc, r: t.r, rv: t.rv, z0: t.zc - t.rv - 3 }));
  // lane markings from the carriageway meshes
  const marks = [];
  for (const m of rr.result.display.meshes) {
    if (m.kind !== 'carriageway') continue;
    const el = elements().find(e => e.kind === 'carriageway');
    const n = el ? el.lanes || 2 : 2;
    for (let j = 1; j < n; j++) {
      const fj = (m.ny - 1) * j / n;
      const j0 = Math.floor(fj), t = fj - j0;
      const P3 = i => { const a = 3 * (i * m.ny + j0), b = 3 * (i * m.ny + Math.min(j0 + 1, m.ny - 1));
        return [0, 1, 2].map(c => m.xyz[a + c] * (1 - t) + m.xyz[b + c] * t); };
      const line = [];
      const ds = m.s[1] - m.s[0];
      const on = Math.max(1, Math.round(3 / ds)), per = Math.max(2, Math.round(9 / ds));
      for (let i = 0; i + on < m.ns; i += per) line.push(P3(i), P3(i + on));
      marks.push(line);
    }
  }
  const al = rr.alignment;
  const iEye = Math.min(al.s.length - 1, 3), iLook = Math.min(al.s.length - 1, 40);
  const lane = (rr.edges.find((e, k) => elements()[k].kind === 'carriageway') || [0, 7]);
  const t1 = (lane[0] + (lane[1] - lane[0]) / 4) - rr.ref_y;
  const pt = (i, t) => [al.x[i] - Math.sin(al.h[i]) * t, al.y[i] + Math.cos(al.h[i]) * t];
  const ze = (i) => { const pv = rr.profile.pvis; return pv.length ? pv[0][1] : 0; };
  const e0 = pt(iEye, t1), e1 = pt(iLook, t1);
  const allE = rr.result.display.meshes.flatMap(m => m.E);
  const allL = rr.result.display.meshes.flatMap(m => m.L || []);
  const iS = Math.min(al.s.length - 1, 70), iT = Math.min(al.s.length - 1, 160);
  const sA = pt(0, -25), sB = pt(iT, t1);
  return { surfaces, poles, trees, marks, labels: [], dims: [], vmax: { E: robustMax(allE), L: robustMax(allL.length ? allL : [1]) }, cct: LUM[R.sel.phot]?.cct || 3000,
    extent: ex, zmin, driver: { eye: [e0[0], e0[1], interpPoleZ(al.s[iEye]) + 1.5], look: [e1[0], e1[1], interpPoleZ(al.s[iLook]) + 0.5] },
    start: { eye: [sA[0] - 35 * Math.cos(al.h[0]), sA[1] - 35 * Math.sin(al.h[0]), interpPoleZ(0) + 38], look: [sB[0], sB[1], interpPoleZ(al.s[iT])] } };
}
function interpPoleZ(s) {
  const p = R.route.poles;
  if (!p.length) return 0;
  if (s <= p[0].s) return p[0].z0;
  for (let i = 0; i + 1 < p.length; i++) if (s >= p[i].s && s <= p[i + 1].s) return p[i].z0 + (p[i + 1].z0 - p[i].z0) * (s - p[i].s) / ((p[i + 1].s - p[i].s) || 1);
  return p[p.length - 1].z0;
}

function refresh3D() {
  if (!v3) return;
  const isRoute = !!R.route && ['layout', 'elec', 'struct', 'energy', 'report'].includes(step);
  const t0 = performance.now();
  const data = isRoute ? routeScene() : sectionScene();
  const t1 = performance.now();
  const lit = isRoute || !!R.eval;
  v3.mode = lit ? viewMode : 'day';
  v3.quantity = viewQty; v3.scale = colourScale;
  const prev = v3._key;
  const key = (isRoute ? 'route' : 'sec') + JSON.stringify(data.extent);
  v3.build(data, prev !== key);
  v3._key = key;
  if (window.SL_DEBUG) console.log('3d scene', (t1 - t0).toFixed(0), 'ms, build', (performance.now() - t1).toFixed(0), 'ms');
  update3DLegend(lit);
  $('#hint3d').innerHTML = lit ? (viewMode === 'night'
    ? '<b>Night view.</b> The road shows the calculated brightness as a driver sees it; footways show illuminance. Drag to orbit, scroll to zoom.'
    : viewMode === 'false' ? '<b>False colour.</b> Calculated values on the scale shown at the left.' : '<b>Day view.</b> The geometry of the design.')
    : '<b>Preview.</b> Strips and a typical column are drawn to scale. Run the design search to light the street.';
}
function update3DLegend(lit = !!R.eval) {
  const el = $('#legend3d');
  if (!lit || viewMode !== 'false' || !v3.data) { el.innerHTML = ''; return; }
  const q = viewQty === 'L' ? 'L' : 'E';
  el.innerHTML = legendSVG(v3.data.vmax[q], q === 'L' ? 'cd/m² (carriageway), lx elsewhere' : 'lx', colourScale, [], 300);
}

export { P, R, LUM };
