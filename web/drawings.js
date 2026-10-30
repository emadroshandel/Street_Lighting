/* Street Lighting — engineering drawings as SVG (plans, isolines, sections, diagrams).
 * Copyright (C) 2026 Emad Roshandel — GPL-3.0-or-later (see LICENSE)
 */
import { SVG, colour, rgb, fmt, isolines, niceLevels, gridImage, esc, robustMax } from './util.js';

const STRIP = {
  carriageway: '#4b5059', footway: '#b9b3a6', cycleway: '#9a6150', median: '#7f9864', verge: '#7f9864',
  parking: '#646a72', shoulder: '#5b6068', kerb: '#cfcac0',
};
export const stripColour = k => STRIP[k] || '#888';
const KIND_LABEL = { carriageway: 'Carriageway', footway: 'Footway', cycleway: 'Cycle track', median: 'Median',
  verge: 'Verge', parking: 'Parking', shoulder: 'Hard shoulder' };
export const kindLabel = k => KIND_LABEL[k] || k;

// ---------------------------------------------------------------------------
// cross-section elevation — the drawing that changes live while editing
// ---------------------------------------------------------------------------
export function crossSection(elements, rows = [], opts = {}) {
  const W = elements.reduce((a, e) => a + (+e.width || 0), 0) || 1;
  const Hmax = Math.max(8, ...rows.map(r => +r.height || 0), ...(opts.trees || []).map(t => +t.height || 0));
  const pad = 2.2;
  const sc = Math.min(760 / (W + 2 * pad), 300 / (Hmax + 3));
  const w = (W + 2 * pad) * sc, h = (Hmax + 4.2) * sc;
  const s = new SVG(Math.max(w, 300), h + 54, 'xsec');
  const X = y => (pad + y) * sc;
  const Z = z => h - (z + 2.4) * sc;
  // light fans (behind everything)
  if (opts.fans !== false) {
    rows.forEach((r, i) => {
      const side = r.side >= 0 ? 1 : -1;
      const yl = r.y + side * (r.overhang || 0);
      const H = r.height;
      const reach = H * 2.2;
      const id = 'fan' + i + Math.random().toString(36).slice(2, 6);
      s.defs.push(`<radialGradient id="${id}" cx="${X(yl)}" cy="${Z(H)}" r="${reach * sc}" gradientUnits="userSpaceOnUse">
        <stop offset="0" stop-color="#ffd27a" stop-opacity="0.55"/><stop offset="1" stop-color="#ffd27a" stop-opacity="0"/></radialGradient>`);
      const a = yl - side * H * 0.5, b = yl + side * H * 1.9;
      s.poly([[X(yl), Z(H - 0.1)], [X(Math.min(a, b)), Z(0)], [X(Math.max(a, b)), Z(0)]], `fill="url(#${id})"`, true);
    });
  }
  // ground and strips
  s.rect(0, Z(0), s.w, 2.4 * sc, 'fill="var(--ground)"');
  let y = 0;
  elements.forEach((e, i) => {
    const wd = +e.width || 0;
    const raised = ['footway', 'median', 'verge', 'cycleway'].includes(e.kind) ? 0.15 : 0;
    s.rect(X(y), Z(raised), wd * sc, (raised + 0.25) * sc, `fill="${stripColour(e.kind)}" stroke="var(--ink)" stroke-width="0.6"`);
    if (e.kind === 'carriageway') {
      const n = Math.max(1, +e.lanes || 1);
      for (let j = 1; j < n; j++) s.line(X(y + wd * j / n), Z(0) - 1, X(y + wd * j / n), Z(0) + 3, 'stroke="#fff" stroke-width="2"');
    }
    // width dimension; narrow strips alternate their labels on two rows so they never overlap
    const narrow = wd * sc < 95;
    const row = narrow && (i % 2) ? 1 : 0;
    const dy = Z(-0.9);
    s.line(X(y), dy, X(y + wd), dy, 'stroke="var(--ink)" stroke-width="0.7" marker-start="url(#tick)" marker-end="url(#tick)"');
    s.line(X(y), Z(raised), X(y), dy + 4, 'stroke="var(--ink)" stroke-width="0.4" stroke-dasharray="2 2"');
    s.text(X(y + wd / 2), dy - 3 + row * 0, fmt(wd, 2) + (narrow ? '' : ' m'), 'text-anchor="middle" class="dim"');
    const name = (e.name || kindLabel(e.kind)) + (e.cls ? ' · ' + e.cls : '');
    s.text(X(y + wd / 2), Z(-1.8) + row * 14, name, `text-anchor="middle" class="lbl${opts.selected === i ? ' sel' : ''}"`);
    y += wd;
  });
  s.line(X(W), Z(0), X(W), Z(-0.9) + 4, 'stroke="var(--ink)" stroke-width="0.4" stroke-dasharray="2 2"');
  s.defs.push('<marker id="tick" viewBox="0 0 6 6" refX="3" refY="3" markerWidth="6" markerHeight="6" orient="auto"><path d="M3 0 L3 6" stroke="currentColor" stroke-width="1.2"/></marker>');
  // trees
  for (const t of opts.trees || []) {
    const yt = +t.y, base = +t.crown_base || 3, top = +t.height || 8, r = +t.crown_radius || 2.5;
    s.rect(X(yt) - 0.15 * sc, Z(base), 0.3 * sc, base * sc, 'fill="#6b4a2f"');
    s.path(`M${X(yt - r)} ${Z((base + top) / 2)} a ${r * sc} ${(top - base) / 2 * sc} 0 1 0 ${2 * r * sc} 0 a ${r * sc} ${(top - base) / 2 * sc} 0 1 0 ${-2 * r * sc} 0`,
      'fill="#4f7d45" fill-opacity="0.85" stroke="#2f5129" stroke-width="0.8"');
  }
  // poles
  rows.forEach(r => {
    const side = r.side >= 0 ? 1 : -1;
    const H = +r.height, oh = +r.overhang || 0;
    const yl = r.y + side * oh;
    s.rect(X(r.y) - 0.09 * sc, Z(H), 0.18 * sc, H * sc, 'fill="#5d6670" stroke="#3a4048" stroke-width="0.5"');
    if (oh > 0) s.path(`M${X(r.y)} ${Z(H - 0.4)} Q ${X(r.y)} ${Z(H)} ${X(r.y + side * Math.min(0.6, oh))} ${Z(H)} L ${X(yl)} ${Z(H)}`,
      'fill="none" stroke="#5d6670" stroke-width="3"');
    const tilt = (+r.tilt || 0) * side;
    s.add(`<g transform="rotate(${-tilt} ${X(yl)} ${Z(H)})"><rect x="${X(yl) - 0.45 * sc}" y="${Z(H) - 2}" width="${0.9 * sc}" height="${0.18 * sc + 2}" rx="2" fill="#2d333a"/>
      <rect x="${X(yl) - 0.35 * sc}" y="${Z(H) + 0.15 * sc}" width="${0.7 * sc}" height="2.5" fill="#ffd27a"/></g>`);
    // height dimension
    const dx = X(r.y) - side * 14;
    s.line(dx, Z(0), dx, Z(H), 'stroke="var(--accent-ink)" stroke-width="0.8"');
    s.line(dx - 4, Z(H), dx + 4, Z(H), 'stroke="var(--accent-ink)" stroke-width="0.8"');
    s.line(dx - 4, Z(0), dx + 4, Z(0), 'stroke="var(--accent-ink)" stroke-width="0.8"');
    s.text(dx - side * 4, Z(H / 2), 'H ' + fmt(H, 1) + ' m', `text-anchor="${side > 0 ? 'end' : 'start'}" class="dim acc"`);
    if (oh > 0) s.text(X((r.y + yl) / 2), Z(H) - 8, 'arm ' + fmt(oh, 1) + ' m', 'text-anchor="middle" class="dim acc"');
    if (r.tilt) s.text(X(yl), Z(H) + 18, fmt(r.tilt, 0) + '°', 'text-anchor="middle" class="dim"');
  });
  return s.toString();
}

// ---------------------------------------------------------------------------
// isolux / isoluminance plan of the straight section (two spans)
// ---------------------------------------------------------------------------
export function sectionPlan(section, cand, result, opt = {}) {
  const disp = result.display;
  const q = opt.quantity === 'L' && disp.L ? 'L' : 'E';
  const Z = disp[q];
  const xs = disp.x, ys = disp.y;
  const W = section.elements.reduce((a, e) => a + (+e.width || 0), 0);
  const x0 = xs[0], x1 = xs[xs.length - 1], y0 = ys[0], y1 = ys[ys.length - 1];
  const sc = Math.min(1000 / (x1 - x0), 420 / (y1 - y0));
  const mL = 70, mT = 26;
  const w = (x1 - x0) * sc + mL + 20, h = (y1 - y0) * sc + mT + 70;
  const s = new SVG(w, h, 'plan');
  const X = x => mL + (x - x0) * sc;
  const Y = y => mT + (y1 - y) * sc;
  let vmax = 0, vmin = Infinity;
  for (const r of Z) for (const v of r) { vmax = Math.max(vmax, v); vmin = Math.min(vmin, v); }
  const scale = opt.scale || 'classic';
  if (opt.map !== false) {
    const img = gridImage(Z, vmax, scale);
    s.add(`<image href="${img}" x="${X(x0)}" y="${Y(y1)}" width="${(x1 - x0) * sc}" height="${(y1 - y0) * sc}" preserveAspectRatio="none" style="image-rendering:auto"/>`);
  }
  // strips outlines
  let yy = 0;
  for (const e of section.elements) {
    s.rect(X(x0), Y(yy + e.width), (x1 - x0) * sc, e.width * sc, 'fill="none" stroke="rgba(255,255,255,0.55)" stroke-width="0.8"');
    s.text(8, Y(yy + e.width / 2) + 4, (e.name || kindLabel(e.kind)).slice(0, 12), 'class="lbl"');
    if (e.kind === 'carriageway') {
      const n = Math.max(1, e.lanes || 1);
      for (let j = 1; j < n; j++) s.line(X(x0), Y(yy + e.width * j / n), X(x1), Y(yy + e.width * j / n),
        'stroke="rgba(255,255,255,0.7)" stroke-width="1" stroke-dasharray="10 10"');
    }
    yy += e.width;
  }
  // isolines with labels
  const levels = opt.levels || niceLevels(vmin, vmax, 7, q === 'E' ? classLevels(section) : []);
  for (const lv of levels) {
    const lines = isolines(xs, ys, Z, lv);
    for (const ln of lines) {
      const pts = ln.map(p => [X(p[0]), Y(p[1])]);
      s.poly(pts, 'fill="none" stroke="rgba(20,20,20,0.85)" stroke-width="0.9"');
      if (pts.length > 10) {
        const k = Math.floor(pts.length / 2);
        const lab = fmt(lv, lv < 1 ? 2 : lv < 10 ? 1 : 0);
        s.add(`<g><rect x="${pts[k][0] - 3 - lab.length * 3}" y="${pts[k][1] - 7}" width="${lab.length * 6 + 6}" height="12" rx="2" fill="rgba(255,255,255,0.85)"/>`);
        s.text(pts[k][0], pts[k][1] + 3, lab, 'text-anchor="middle" class="iso"');
        s.add('</g>');
      }
    }
  }
  // calculation grid points (EN 13201-3)
  if (opt.points) {
    for (const a of result.areas) {
      for (const gx of a.grid_x) for (const gy of a.grid_y) s.circle(X(gx), Y(gy), 1.3, 'fill="#fff" fill-opacity="0.7"');
    }
  }
  // luminaires / poles for both spans
  for (const r of cand.rows) {
    const side = r.side >= 0 ? 1 : -1;
    for (let k = -1; k <= 2; k++) {
      const x = (r.phase || 0) * cand.S + k * cand.S;
      if (x < x0 - 0.01 || x > x1 + 0.01) continue;
      const yl = r.y + side * r.overhang;
      s.line(X(x), Y(r.y), X(x), Y(yl), 'stroke="#111" stroke-width="2"');
      s.circle(X(x), Y(r.y), 3.5, 'fill="#2d333a" stroke="#fff" stroke-width="1"');
      s.rect(X(x) - 7, Y(yl) - 3, 14, 6, 'fill="#ffd27a" stroke="#111" stroke-width="0.8"');
    }
  }
  // spacing dimension
  const yd = Y(y0) + 22;
  s.line(X(0), yd, X(cand.S), yd, 'stroke="var(--ink)" stroke-width="0.9"');
  s.line(X(0), yd - 5, X(0), yd + 5, 'stroke="var(--ink)"');
  s.line(X(cand.S), yd - 5, X(cand.S), yd + 5, 'stroke="var(--ink)"');
  s.text(X(cand.S / 2), yd - 5, 'S = ' + fmt(cand.S, 2) + ' m', 'text-anchor="middle" class="dim"');
  // scale bar
  const bar = niceStep((x1 - x0) / 5);
  s.rect(X(x1) - bar * sc, yd + 14, bar * sc, 5, 'fill="var(--ink)"');
  s.text(X(x1) - bar * sc / 2, yd + 32, bar + ' m', 'text-anchor="middle" class="dim"');
  return { svg: s.toString(), vmax, vmin, levels, unit: q === 'L' ? 'cd/m²' : 'lx' };
}

function classLevels(section) {
  return [];
}
export function niceStep(v) {
  const m = Math.pow(10, Math.floor(Math.log10(v)));
  return [1, 2, 5, 10].map(k => k * m).find(k => k >= v * 0.7) || m;
}

// ---------------------------------------------------------------------------
// route plan with isolines from the route meshes
// ---------------------------------------------------------------------------
export function routePlan(route, opt = {}) {
  const meshes = route.result.display.meshes;
  const q = opt.quantity || 'E';
  let xmin = Infinity, xmax = -Infinity, ymin = Infinity, ymax = -Infinity;
  for (const m of meshes) for (let k = 0; k < m.xyz.length; k += 3) {
    xmin = Math.min(xmin, m.xyz[k]); xmax = Math.max(xmax, m.xyz[k]);
    ymin = Math.min(ymin, m.xyz[k + 1]); ymax = Math.max(ymax, m.xyz[k + 1]);
  }
  const pad = 12;
  xmin -= pad; xmax += pad; ymin -= pad; ymax += pad;
  const sc = Math.min(1400 / (xmax - xmin), 900 / (ymax - ymin));
  const w = (xmax - xmin) * sc, h = (ymax - ymin) * sc;
  const s = new SVG(w, h, 'plan route');
  const X = x => (x - xmin) * sc, Y = y => (ymax - y) * sc;
  let vmin = Infinity;
  const all = [];
  for (const m of meshes) {
    const vals = q === 'L' ? m.L : m.E;
    if (!vals) continue;
    for (const v of vals) { all.push(v); vmin = Math.min(vmin, v); }
  }
  const vmax = robustMax(all, 0.97);
  const scale = opt.scale || 'classic';
  // filled quads (coarsened for size)
  for (const m of meshes) {
    const vals = (q === 'L' && m.L) ? m.L : m.E;
    const step = Math.max(1, Math.floor(m.ns / 700));
    const paint = q === 'L' && !m.L ? false : true;
    for (let i = 0; i < m.ns - step; i += step) {
      for (let j = 0; j < m.ny - 1; j++) {
        const k = [i * m.ny + j, (i + step) * m.ny + j, (i + step) * m.ny + j + 1, i * m.ny + j + 1];
        const v = (vals[k[0]] + vals[k[1]] + vals[k[2]] + vals[k[3]]) / 4;
        const c = paint && opt.map !== false ? rgb(colour(v / (vmax || 1), scale)) : stripColour(m.kind);
        s.poly(k.map(kk => [X(m.xyz[3 * kk]), Y(m.xyz[3 * kk + 1])]), `fill="${c}" stroke="${c}" stroke-width="0.4"`, true);
      }
    }
  }
  // isolines computed in (y, s) mesh space and mapped to the world
  const levels = opt.levels || niceLevels(vmin, vmax, 6);
  for (const m of meshes) {
    const vals = (q === 'L' && m.L) ? m.L : (q === 'L' ? null : m.E);
    if (!vals) continue;
    const Zg = [];
    for (let i = 0; i < m.ns; i++) Zg.push(vals.slice(i * m.ny, (i + 1) * m.ny));
    const jj = m.y.map((_, j) => j), ii = m.s.map((_, i) => i);
    for (const lv of levels) {
      for (const ln of isolines(jj, ii, Zg, lv)) {
        const pts = ln.map(([fj, fi]) => meshPoint(m, fi, fj)).map(p => [X(p[0]), Y(p[1])]);
        s.poly(pts, 'fill="none" stroke="rgba(15,15,15,0.8)" stroke-width="0.7"');
        if (pts.length > 25) {
          const k = Math.floor(pts.length / 2);
          s.text(pts[k][0], pts[k][1] - 2, fmt(lv, lv < 1 ? 2 : lv < 10 ? 1 : 0), 'text-anchor="middle" class="iso small"');
        }
      }
    }
  }
  // edges
  for (const m of meshes) {
    for (const j of [0, m.ny - 1]) {
      const pts = [];
      for (let i = 0; i < m.ns; i += Math.max(1, Math.floor(m.ns / 400))) pts.push([X(m.xyz[3 * (i * m.ny + j)]), Y(m.xyz[3 * (i * m.ny + j) + 1])]);
      s.poly(pts, 'fill="none" stroke="rgba(255,255,255,0.6)" stroke-width="0.8"');
    }
  }
  // trees
  for (const t of route.result.trees || []) s.circle(X(t.x), Y(t.y), t.r * sc, 'fill="#3f7a3a" fill-opacity="0.55" stroke="#1f4a1f" stroke-width="0.6"');
  // cables
  if (opt.electrical) {
    const palette = ['#e0457b', '#2f9de0', '#9b59d0', '#e07b2f', '#20a39e', '#c0392b'];
    opt.electrical.feeders.forEach((f, i) => {
      const pil = opt.electrical.pillars.find(p => p.id === f.pillar);
      const pts = [[X(pil.x), Y(pil.yw)], ...f.poles.map(p => [X(p.x), Y(p.yw)])];
      s.poly(pts, `fill="none" stroke="${palette[i % palette.length]}" stroke-width="2" stroke-dasharray="6 3"`);
    });
    for (const p of opt.electrical.pillars) {
      s.rect(X(p.x) - 7, Y(p.yw) - 5, 14, 10, 'fill="#1a3550" stroke="#fff" stroke-width="1"');
      s.text(X(p.x) + 10, Y(p.yw) - 7, p.id, 'class="tag"');
    }
  }
  // poles
  for (const L of route.result.luminaires) {
    const pb = L.pole;
    s.line(X(pb[0]), Y(pb[1]), X(L.x), Y(L.y), 'stroke="#111" stroke-width="1.6"');
    s.circle(X(pb[0]), Y(pb[1]), 3, 'fill="#2d333a" stroke="#fff" stroke-width="0.8"');
    s.circle(X(L.x), Y(L.y), 3.2, 'fill="#ffd27a" stroke="#111" stroke-width="0.8"');
    if (opt.ids) s.text(X(pb[0]) + 5, Y(pb[1]) + 12, L.id, 'class="tag small"');
  }
  // chainage
  const al = route.alignment;
  for (let i = 0; i < al.s.length; i++) {
    if (Math.abs(al.s[i] / 50 - Math.round(al.s[i] / 50)) < 1e-6 || i === 0) {
      s.circle(X(al.x[i]), Y(al.y[i]), 2, 'fill="var(--ink)"');
      s.text(X(al.x[i]) + 4, Y(al.y[i]) - 4, 'ch ' + Math.round(al.s[i]), 'class="tag small"');
    }
  }
  return { svg: s.toString(), vmax, vmin, levels, unit: q === 'L' ? 'cd/m²' : 'lx' };
}

function meshPoint(m, fi, fj) {
  const i0 = Math.max(0, Math.min(m.ns - 2, Math.floor(fi))), j0 = Math.max(0, Math.min(m.ny - 2, Math.floor(fj)));
  const u = fi - i0, v = fj - j0;
  const P = (i, j) => { const k = 3 * (i * m.ny + j); return [m.xyz[k], m.xyz[k + 1]]; };
  const a = P(i0, j0), b = P(i0 + 1, j0), c = P(i0 + 1, j0 + 1), d = P(i0, j0 + 1);
  return [0, 1].map(t => (1 - u) * (1 - v) * a[t] + u * (1 - v) * b[t] + u * v * c[t] + (1 - u) * v * d[t]);
}

// ---------------------------------------------------------------------------
// vertical profile with poles
// ---------------------------------------------------------------------------
export function profileSVG(route) {
  const al = route.alignment;
  const pv = route.profile.pvis;
  const L = al.length;
  const zOf = s => {
    let z = pv.length ? pv[0][1] : 0;
    for (let i = 0; i + 1 < pv.length; i++) if (s >= pv[i][0] && s <= pv[i + 1][0]) z = pv[i][1] + (pv[i + 1][1] - pv[i][1]) * (s - pv[i][0]) / ((pv[i + 1][0] - pv[i][0]) || 1);
    return z;
  };
  const pts = route.poles.map(p => [p.s, p.z0, p.z0 + p.H]);
  const zs = pts.length ? pts.flatMap(p => [p[1], p[2]]) : [0, 10];
  const zmin = Math.min(...zs) - 2, zmax = Math.max(...zs) + 2;
  const w = 1000, h = 220, mL = 50, mB = 30;
  const sx = (w - mL - 10) / L, sz = (h - mB - 10) / (zmax - zmin);
  const s = new SVG(w, h, 'profile');
  const X = v => mL + v * sx, Y = z => h - mB - (z - zmin) * sz;
  const ground = [];
  for (let v = 0; v <= L; v += L / 200) ground.push([X(v), Y(route.poles.length ? interpZ(route.poles, v) : zOf(v))]);
  s.poly([[X(0), h - mB], ...ground, [X(L), h - mB]], 'fill="var(--ground)" stroke="var(--ink)" stroke-width="1"', true);
  for (const p of route.poles) {
    s.line(X(p.s), Y(p.z0), X(p.s), Y(p.z0 + p.H), 'stroke="#5d6670" stroke-width="1.6"');
    s.circle(X(p.s), Y(p.z0 + p.H), 2.5, 'fill="#ffd27a" stroke="#111" stroke-width="0.6"');
  }
  for (const c of route.profile.curves || []) {
    s.text(X(c.s), 14, (c.type === 'crest' ? 'crest ' : 'sag ') + fmt(c.g1, 1) + '% → ' + fmt(c.g2, 1) + '%', 'text-anchor="middle" class="tag small"');
  }
  for (let v = 0; v <= L; v += niceStep(L / 8)) s.text(X(v), h - 10, 'ch ' + Math.round(v), 'text-anchor="middle" class="tag small"');
  s.text(4, Y(zmax) + 10, fmt(zmax, 0) + ' m', 'class="tag small"');
  s.text(4, Y(zmin), fmt(zmin, 0) + ' m', 'class="tag small"');
  return s.toString();
}
function interpZ(poles, s) {
  const p = poles;
  if (s <= p[0].s) return p[0].z0;
  for (let i = 0; i + 1 < p.length; i++) if (s >= p[i].s && s <= p[i + 1].s) return p[i].z0 + (p[i + 1].z0 - p[i].z0) * (s - p[i].s) / ((p[i + 1].s - p[i].s) || 1);
  return p[p.length - 1].z0;
}

// ---------------------------------------------------------------------------
// polar intensity diagram (cd/klm)
// ---------------------------------------------------------------------------
export function polarSVG(pol, size = 300, planes = [['0', '180', '#2f6fb3', 'C0–C180'], ['90', '270', '#d08a1e', 'C90–C270']]) {
  const s = new SVG(size, size + 26, 'polar');
  const c = size / 2, R = size / 2 - 18;
  let imax = 0;
  for (const [a, b] of planes) for (const v of [...pol[a], ...pol[b]]) imax = Math.max(imax, v);
  const ring = niceStep(imax / 4);
  const rmax = Math.ceil(imax / ring) * ring || 1;
  for (let r = ring; r <= rmax + 1e-9; r += ring) {
    s.circle(c, c, R * r / rmax, 'fill="none" stroke="var(--line)" stroke-width="0.6"');
    s.text(c + 3, c + R * r / rmax - 2, fmt(r, 0), 'class="tag small"');
  }
  for (let a = 0; a < 360; a += 30) {
    const t = a * Math.PI / 180;
    s.line(c, c, c + R * Math.sin(t), c + R * Math.cos(t), 'stroke="var(--line)" stroke-width="0.5"');
  }
  const g = pol.gamma;
  for (const [a, b, col] of planes) {
    const pts = [];
    g.forEach((gm, i) => { const t = gm * Math.PI / 180; const r = R * pol[a][i] / rmax; pts.push([c - r * Math.sin(t), c + r * Math.cos(t)]); });
    for (let i = g.length - 1; i >= 0; i--) { const t = g[i] * Math.PI / 180; const r = R * pol[b][i] / rmax; pts.push([c + r * Math.sin(t), c + r * Math.cos(t)]); }
    s.poly(pts, `fill="${col}" fill-opacity="0.12" stroke="${col}" stroke-width="1.6"`, true);
  }
  planes.forEach(([, , col, lab], i) => {
    s.rect(10 + i * 120, size + 8, 14, 4, `fill="${col}"`);
    s.text(28 + i * 120, size + 13, lab, 'class="tag small"');
  });
  s.text(size - 8, size + 13, 'cd/klm', 'text-anchor="end" class="tag small"');
  return s.toString();
}

// ---------------------------------------------------------------------------
// column and foundation elevation
// ---------------------------------------------------------------------------
export function columnSVG(st, H, oh) {
  const col = st.column, f = st.foundation;
  const depth = f.depth;
  const total = H + depth + 1;
  const h = 420, sc = (h - 30) / total, w = 300;
  const s = new SVG(w, h, 'column');
  const gx = 120, gy = 15 + H * sc;
  s.rect(0, gy, w, h - gy, 'fill="var(--ground)"');
  s.rect(gx - f.diameter / 2 * sc, gy, f.diameter * sc, depth * sc, 'fill="#b8b2a6" stroke="var(--ink)" stroke-width="0.8"');
  const db = col.D_base * sc * 6, dt = col.D_top * sc * 6;
  s.poly([[gx - db / 2, gy + 0.8 * depth * sc], [gx - dt / 2, gy - H * sc], [gx + dt / 2, gy - H * sc], [gx + db / 2, gy + 0.8 * depth * sc]],
    'fill="#8d949c" stroke="#3a4048" stroke-width="0.8"', true);
  if (oh > 0) s.line(gx, gy - H * sc, gx + oh * sc, gy - H * sc, 'stroke="#5d6670" stroke-width="3"');
  s.rect(gx + oh * sc - 14, gy - H * sc - 4, 28, 7, 'fill="#2d333a"');
  s.text(gx - 60, gy - H * sc / 2, 'H ' + fmt(H, 1) + ' m', 'text-anchor="end" class="dim"');
  s.text(gx + 40, gy + depth * sc / 2, 'depth ' + fmt(depth, 2) + ' m', 'class="dim"');
  s.text(gx + 40, gy + depth * sc / 2 + 14, 'Ø ' + fmt(f.diameter, 2) + ' m', 'class="dim"');
  s.text(gx + 20, gy - 6, 'base Ø' + fmt(col.D_base * 1000, 0) + ' × ' + fmt(col.t * 1000, 0) + ' mm', 'class="dim"');
  s.text(gx + 20, gy - H * sc + 20, 'top Ø' + fmt(col.D_top * 1000, 0) + ' mm', 'class="dim"');
  return s.toString();
}

// ---------------------------------------------------------------------------
// single-line diagram
// ---------------------------------------------------------------------------
export function sldSVG(el) {
  const blocks = el.sld;
  const rowsH = blocks.reduce((a, b) => a + 140 + b.feeders.length * 46, 0);
  const s = new SVG(860, rowsH + 20, 'sld');
  let y = 20;
  for (const b of blocks) {
    const x = 40;
    s.text(x, y, b.pillar + ' — feeder pillar', 'class="h"');
    s.text(x, y + 16, b.supply, 'class="tag"');
    const bus = y + 60;
    s.line(x + 10, y + 22, x + 10, bus, 'stroke="var(--ink)" stroke-width="1.4"');
    s.rect(x - 2, y + 26, 24, 14, 'fill="none" stroke="var(--ink)"');
    s.text(x + 34, y + 37, 'kWh  ·  ' + b.main, 'class="tag"');
    s.text(x + 34, y + 51, b.spd + '  ·  ' + b.control, 'class="tag small"');
    s.line(x + 10, bus, 820, bus, 'stroke="var(--ink)" stroke-width="2.2"');
    s.text(x + 34, bus - 4, 'L1 L2 L3 N PE', 'class="tag small"');
    let fy = bus + 30;
    for (const f of b.feeders) {
      s.line(x + 60, bus, x + 60, fy, 'stroke="var(--ink)" stroke-width="1.2"');
      s.line(x + 60, fy, x + 120, fy, 'stroke="var(--ink)" stroke-width="1.2"');
      s.rect(x + 120, fy - 9, 60, 18, `fill="${f.ok ? 'var(--ok-bg)' : 'var(--bad-bg)'}" stroke="var(--ink)"`);
      s.text(x + 150, fy + 4, f.device, 'text-anchor="middle" class="tag"');
      s.line(x + 180, fy, x + 520, fy, 'stroke="var(--accent-ink)" stroke-width="1.6" stroke-dasharray="7 3"');
      s.text(x + 190, fy - 5, f.id + '  ' + f.cable + '  ' + fmt(f.length, 0) + ' m', 'class="tag"');
      for (let k = 0; k < Math.min(f.n, 12); k++) s.circle(x + 530 + k * 20, fy, 6, 'fill="#ffd27a" stroke="#111" stroke-width="0.6"');
      s.text(x + 530, fy + 22, f.n + ' luminaires · ' + fmt(f.load_W, 0) + ' W · ΔU ' + fmt(f.du, 2) + ' %', 'class="tag small"');
      fy += 46;
    }
    s.text(x, fy + 8, b.earth, 'class="tag small"');
    y = fy + 40;
  }
  return s.toString();
}

// ---------------------------------------------------------------------------
// span-by-span bar chart
// ---------------------------------------------------------------------------
export function spansChart(area, key, req, unit) {
  const sp = area.spans;
  const w = 1000, h = 190, mL = 46, mB = 34;
  const vmax = Math.max(req || 0, ...sp.map(d => d[key] || 0)) * 1.15 || 1;
  const s = new SVG(w, h, 'chart');
  const L = sp.length ? sp[sp.length - 1].s1 : 1, s0 = sp.length ? sp[0].s0 : 0;
  const X = v => mL + (v - s0) / (L - s0 || 1) * (w - mL - 10), Y = v => h - mB - v / vmax * (h - mB - 12);
  for (const d of sp) {
    const v = d[key] || 0;
    const ok = d.checks.every(c => c.ok);
    s.rect(X(d.s0) + 1, Y(v), X(d.s1) - X(d.s0) - 2, Y(0) - Y(v), `fill="${ok ? 'var(--ok)' : 'var(--bad)'}" fill-opacity="0.75"`);
  }
  if (req) {
    s.line(mL, Y(req), w - 10, Y(req), 'stroke="var(--ink)" stroke-dasharray="5 4" stroke-width="1"');
    s.text(w - 12, Y(req) - 4, 'required ' + fmt(req, 2) + ' ' + unit, 'text-anchor="end" class="tag small"');
  }
  for (const t of niceLevels(0, vmax, 4)) { s.text(mL - 6, Y(t) + 3, fmt(t, t < 1 ? 2 : 1), 'text-anchor="end" class="tag small"'); }
  for (let v = 0; v <= L; v += niceStep(L / 8)) s.text(X(v), h - 12, 'ch ' + Math.round(v), 'text-anchor="middle" class="tag small"');
  return s.toString();
}

export function bars(items, unit, w = 460) {
  const h = 26 * items.length + 10;
  const s = new SVG(w, h, 'chart');
  const vmax = Math.max(...items.map(i => i.v)) || 1;
  items.forEach((it, i) => {
    const y = 6 + i * 26;
    s.text(150, y + 14, it.label, 'text-anchor="end" class="tag"');
    s.rect(158, y + 3, (w - 230) * it.v / vmax, 16, `fill="${it.c || 'var(--accent)'}"`);
    s.text(162 + (w - 230) * it.v / vmax, y + 15, fmt(it.v, it.d ?? 0) + ' ' + unit, 'class="tag"');
  });
  return s.toString();
}
