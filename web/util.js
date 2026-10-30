/* Street Lighting — shared helpers: engine access, colour scales, isolines, SVG.
 * Copyright (C) 2026 Emad Roshandel — GPL-3.0-or-later (see LICENSE)
 */
'use strict';

// ---------------------------------------------------------------------------
// engine: local server (desktop) or Pyodide worker (GitHub Pages / offline file)
// ---------------------------------------------------------------------------
const engine = { mode: 'unknown', worker: null, pending: new Map(), seq: 0 };

export async function startEngine(onProgress) {
  if (location.protocol !== 'file:') {
    try {
      const r = await fetch('../api/health', { cache: 'no-store' });
      if (r.ok && (await r.json()).ok) { engine.mode = 'server'; return 'server'; }
    } catch (e) { /* fall through to the browser engine */ }
  }
  engine.mode = 'browser';
  const base = new URL('../', location.href).href;
  engine.worker = new Worker('worker.js');
  await new Promise((resolve, reject) => {
    engine.worker.onmessage = (e) => {
      const d = e.data;
      if (d.type === 'progress') onProgress && onProgress(d.msg, d.pct);
      else if (d.type === 'ready') resolve();
      else if (d.type === 'fatal') reject(new Error(d.msg));
      else if (d.type === 'result') {
        const p = engine.pending.get(d.id);
        if (p) { engine.pending.delete(d.id); p(d.out); }
      }
    };
    engine.worker.postMessage({ type: 'boot', base });
  });
  return 'browser';
}

export async function api(path, body) {
  let txt;
  if (engine.mode === 'server') {
    const r = await fetch('../api' + path, { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {}) });
    txt = await r.text();
  } else {
    const id = ++engine.seq;
    txt = await new Promise(res => {
      engine.pending.set(id, res);
      engine.worker.postMessage({ type: 'call', id, path: '/api' + path, body: JSON.stringify(body || {}) });
    });
  }
  let j;
  try { j = JSON.parse(txt); } catch (e) { throw new Error('The engine returned an unreadable answer.'); }
  if (j && j.error) throw new Error(j.error);
  return j;
}
export const engineMode = () => engine.mode;

// ---------------------------------------------------------------------------
// small helpers
// ---------------------------------------------------------------------------
export const $ = (s, el = document) => el.querySelector(s);
export const $$ = (s, el = document) => [...el.querySelectorAll(s)];
export const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
export function fmt(v, d = 2) {
  if (v === null || v === undefined || Number.isNaN(v)) return '–';
  if (typeof v !== 'number') return String(v);
  return v.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
}
export function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
// The desktop window (pywebview) does not let a page download files, so there the file is handed
// to Python, which shows a native "Save as" dialog. In a browser the usual download is used.
function desktopApi() { return window.pywebview && window.pywebview.api && window.pywebview.api.save_file; }
async function desktopSave(name, data, isDataURL) {
  try {
    const r = await window.pywebview.api.save_file(name, data, !!isDataURL);
    if (r && r.saved) toast('Saved ' + r.path, 'ok', 5000);
    else if (r && r.error) toast('Could not save the file: ' + r.error, 'error', 8000);
  } catch (e) { toast('Could not save the file: ' + (e && e.message || e), 'error', 8000); }
}
export function download(name, text, type = 'text/plain') {
  if (desktopApi()) return desktopSave(name, text, false);
  const blob = new Blob([text], { type });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500);
}
export function downloadDataURL(name, url) {
  if (desktopApi()) return desktopSave(name, url, true);
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => a.remove(), 500);
}
export function readFile(file) {
  return new Promise((res, rej) => {
    const r = new FileReader();
    r.onload = () => res(r.result);
    r.onerror = rej;
    r.readAsText(file, 'latin1');
  });
}
// A short message in the corner. Errors are announced at once (role=alert), others politely.
// `action` = { label, fn } adds a button, e.g. Undo; click the message to dismiss it.
export function toast(msg, kind = 'info', ms = 4200, action = null) {
  let host = $('#toasts');
  const el = document.createElement('div');
  el.className = 'toast ' + kind;
  el.setAttribute('role', kind === 'error' ? 'alert' : 'status');
  const t = document.createElement('span');
  t.textContent = msg;
  el.appendChild(t);
  const close = () => { el.classList.add('out'); setTimeout(() => el.remove(), 400); };
  if (action) {
    const b = document.createElement('button');
    b.className = 'toastact';
    b.textContent = action.label;
    b.onclick = ev => { ev.stopPropagation(); action.fn(); close(); };
    el.appendChild(b);
  }
  el.title = 'Click to dismiss';
  el.onclick = close;
  host.appendChild(el);
  let timer = setTimeout(close, ms);
  // keep it while the pointer or keyboard focus is on it, so there is time to read or press Undo
  el.onmouseenter = el.onfocusin = () => clearTimeout(timer);
  el.onmouseleave = () => { clearTimeout(timer); timer = setTimeout(close, 2000); };
}

// ---------------------------------------------------------------------------
// colour scales
// "night" mimics how lit asphalt looks: dark blue-grey -> warm amber -> white
// "classic" is the familiar engineering false-colour scale
// ---------------------------------------------------------------------------
const SCALES = {
  night: [[0, [14, 22, 38]], [0.18, [40, 52, 78]], [0.38, [120, 86, 60]], [0.58, [214, 150, 58]],
    [0.78, [250, 206, 112]], [1, [255, 250, 232]]],
  classic: [[0, [36, 30, 120]], [0.2, [30, 110, 210]], [0.4, [40, 190, 170]], [0.6, [150, 210, 60]],
    [0.8, [250, 190, 40]], [1, [220, 40, 40]]],
};
export function colour(t, scale = 'night') {
  const s = SCALES[scale] || SCALES.night;
  t = clamp(t, 0, 1);
  for (let i = 1; i < s.length; i++) {
    if (t <= s[i][0]) {
      const [a, ca] = s[i - 1], [b, cb] = s[i];
      const u = (t - a) / (b - a || 1);
      return ca.map((c, k) => Math.round(c + (cb[k] - c) * u));
    }
  }
  return s[s.length - 1][1];
}
export const rgb = c => `rgb(${c[0]},${c[1]},${c[2]})`;

// ---------------------------------------------------------------------------
// isolines (marching squares) — Z[iy][ix] on coordinates xs, ys
// ---------------------------------------------------------------------------
export function niceLevels(vmin, vmax, n = 8, extra = []) {
  if (!(vmax > 0)) return [];
  const lo = Math.max(vmin, vmax / 200);
  const raw = (vmax - lo) / n;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map(m => m * mag).reduce((a, b) => Math.abs(b - raw) < Math.abs(a - raw) ? b : a);
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v < vmax; v += step) out.push(+v.toPrecision(6));
  for (const e of extra) if (e > vmin && e < vmax && !out.some(v => Math.abs(v - e) < step * 0.1)) out.push(e);
  return out.sort((a, b) => a - b);
}

export function isolines(xs, ys, Z, level) {
  const segs = [];
  const ny = Z.length, nx = Z[0].length;
  const tbl = { 1: [[3, 0]], 2: [[0, 1]], 3: [[3, 1]], 4: [[1, 2]], 5: [[3, 2], [0, 1]], 6: [[0, 2]], 7: [[3, 2]],
    8: [[2, 3]], 9: [[0, 2]], 10: [[0, 3], [1, 2]], 11: [[1, 2]], 12: [[1, 3]], 13: [[0, 1]], 14: [[0, 3]] };
  const E = [[0, 1], [1, 2], [2, 3], [3, 0]];
  for (let j = 0; j < ny - 1; j++) {
    for (let i = 0; i < nx - 1; i++) {
      const z = [Z[j][i], Z[j][i + 1], Z[j + 1][i + 1], Z[j + 1][i]];
      let c = 0;
      for (let k = 0; k < 4; k++) if (z[k] >= level) c |= 1 << k;
      if (c === 0 || c === 15) continue;
      const P = [[xs[i], ys[j]], [xs[i + 1], ys[j]], [xs[i + 1], ys[j + 1]], [xs[i], ys[j + 1]]];
      const edge = (e) => {
        const [a, b] = E[e];
        const t = z[b] !== z[a] ? (level - z[a]) / (z[b] - z[a]) : 0.5;
        return [P[a][0] + t * (P[b][0] - P[a][0]), P[a][1] + t * (P[b][1] - P[a][1])];
      };
      for (const [ea, eb] of tbl[c]) segs.push([edge(ea), edge(eb)]);
    }
  }
  return joinSegments(segs);
}

function joinSegments(segs) {
  const key = p => Math.round(p[0] * 1e5) + ',' + Math.round(p[1] * 1e5);
  const map = new Map();
  segs.forEach((s, k) => {
    for (const p of s) { const kk = key(p); if (!map.has(kk)) map.set(kk, []); map.get(kk).push(k); }
  });
  const used = new Array(segs.length).fill(false);
  const lines = [];
  for (let k = 0; k < segs.length; k++) {
    if (used[k]) continue;
    used[k] = true;
    const line = [segs[k][0], segs[k][1]];
    for (const dir of [1, -1]) {
      for (;;) {
        const tip = dir === 1 ? line[line.length - 1] : line[0];
        const cand = (map.get(key(tip)) || []).find(j => !used[j]);
        if (cand === undefined) break;
        used[cand] = true;
        const [p, q] = segs[cand];
        const other = key(p) === key(tip) ? q : p;
        if (dir === 1) line.push(other); else line.unshift(other);
      }
    }
    lines.push(line);
  }
  return lines;
}

// ---------------------------------------------------------------------------
// SVG builder
// ---------------------------------------------------------------------------
export class SVG {
  constructor(w, h, cls = '') { this.w = w; this.h = h; this.parts = []; this.cls = cls; this.defs = []; }
  add(s) { this.parts.push(s); return this; }
  line(x1, y1, x2, y2, a = '') { return this.add(`<line x1="${x1.toFixed(2)}" y1="${y1.toFixed(2)}" x2="${x2.toFixed(2)}" y2="${y2.toFixed(2)}" ${a}/>`); }
  rect(x, y, w, h, a = '') { return this.add(`<rect x="${x.toFixed(2)}" y="${y.toFixed(2)}" width="${Math.max(w, 0).toFixed(2)}" height="${Math.max(h, 0).toFixed(2)}" ${a}/>`); }
  circle(x, y, r, a = '') { return this.add(`<circle cx="${x.toFixed(2)}" cy="${y.toFixed(2)}" r="${r.toFixed(2)}" ${a}/>`); }
  path(d, a = '') { return this.add(`<path d="${d}" ${a}/>`); }
  poly(pts, a = '', closed = false) {
    if (!pts.length) return this;
    const d = pts.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(2) + ' ' + p[1].toFixed(2)).join('') + (closed ? 'Z' : '');
    return this.path(d, a);
  }
  text(x, y, s, a = '') { return this.add(`<text x="${x.toFixed(2)}" y="${y.toFixed(2)}" ${a}>${esc(s)}</text>`); }
  toString() {
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${this.w} ${this.h}" class="${this.cls}" role="img">` +
      (this.defs.length ? `<defs>${this.defs.join('')}</defs>` : '') + this.parts.join('') + '</svg>';
  }
}

// raster image (data URL) of a grid in a colour scale — for maps inside SVG
export function gridImage(Z, vmax, scale = 'night', vmin = 0) {
  const ny = Z.length, nx = Z[0].length;
  const c = document.createElement('canvas');
  c.width = nx; c.height = ny;
  const ctx = c.getContext('2d');
  const img = ctx.createImageData(nx, ny);
  for (let j = 0; j < ny; j++) {
    for (let i = 0; i < nx; i++) {
      const v = Z[j][i];
      const t = vmax > vmin ? (v - vmin) / (vmax - vmin) : 0;
      const col = colour(scale === 'night' ? Math.pow(clamp(t, 0, 1), 0.65) : t, scale);
      const k = ((ny - 1 - j) * nx + i) * 4;          // flip: row 0 at the bottom
      img.data[k] = col[0]; img.data[k + 1] = col[1]; img.data[k + 2] = col[2]; img.data[k + 3] = 255;
    }
  }
  ctx.putImageData(img, 0, 0);
  return c.toDataURL();
}

export function legendSVG(vmax, unit, scale = 'night', levels = [], w = 300, vmin = 0) {
  const s = new SVG(w, 46, 'legendsvg');
  const id = 'lg' + Math.random().toString(36).slice(2, 8);
  const stops = [];
  for (let i = 0; i <= 20; i++) {
    const t = i / 20;
    stops.push(`<stop offset="${t}" stop-color="${rgb(colour(scale === 'night' ? Math.pow(t, 0.65) : t, scale))}"/>`);
  }
  s.defs.push(`<linearGradient id="${id}">${stops.join('')}</linearGradient>`);
  s.rect(10, 6, w - 20, 14, `fill="url(#${id})" stroke="var(--line)" stroke-width="0.5"`);
  const ticks = levels.length ? levels : niceLevels(vmin, vmax, 5);
  for (const v of ticks) {
    const x = 10 + (w - 20) * (v - vmin) / (vmax - vmin || 1);
    if (x < 10 || x > w - 10) continue;
    s.line(x, 20, x, 25, 'stroke="currentColor" stroke-width="0.8"');
    s.text(x, 36, fmt(v, v < 1 ? 2 : v < 10 ? 1 : 0), 'text-anchor="middle" font-size="9" fill="currentColor"');
  }
  s.text(w - 10, 46, unit, 'text-anchor="end" font-size="9" fill="currentColor"');
  return s.toString();
}

// robust upper value for colour scales (ignores a few hot spots under luminaires)
export function robustMax(values, q = 0.98) {
  const a = Array.from(values).filter(v => Number.isFinite(v)).sort((x, y) => x - y);
  if (!a.length) return 1;
  return Math.max(a[Math.min(a.length - 1, Math.floor(q * (a.length - 1)))], 1e-6);
}

// wheel-zoom and drag-pan for a static SVG drawing
export function panZoom(svg) {
  if (!svg || svg._pz) return;
  svg._pz = true;
  const vb = svg.getAttribute('viewBox').split(/\s+/).map(Number);
  const v0 = [...vb];
  const set = () => svg.setAttribute('viewBox', vb.map(v => v.toFixed(2)).join(' '));
  svg.style.cursor = 'grab';
  svg.addEventListener('wheel', e => {
    e.preventDefault();
    const r = svg.getBoundingClientRect();
    const px = vb[0] + (e.clientX - r.left) / r.width * vb[2], py = vb[1] + (e.clientY - r.top) / r.height * vb[3];
    const f = e.deltaY > 0 ? 1.18 : 1 / 1.18;
    vb[2] = Math.min(v0[2] * 1.2, Math.max(v0[2] / 60, vb[2] * f));
    vb[3] = vb[2] * v0[3] / v0[2];
    vb[0] = px - (e.clientX - r.left) / r.width * vb[2];
    vb[1] = py - (e.clientY - r.top) / r.height * vb[3];
    set();
  }, { passive: false });
  let drag = null;
  svg.addEventListener('pointerdown', e => { drag = { x: e.clientX, y: e.clientY, vb: [...vb] }; svg.setPointerCapture(e.pointerId); svg.style.cursor = 'grabbing'; });
  svg.addEventListener('pointermove', e => {
    if (!drag) return;
    const r = svg.getBoundingClientRect();
    vb[0] = drag.vb[0] - (e.clientX - drag.x) / r.width * vb[2];
    vb[1] = drag.vb[1] - (e.clientY - drag.y) / r.height * vb[3];
    set();
  });
  svg.addEventListener('pointerup', () => { drag = null; svg.style.cursor = 'grab'; });
  svg.addEventListener('dblclick', () => { vb.splice(0, 4, ...v0); set(); });
}
