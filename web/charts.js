/* Street Lighting — interactive charts (D3).
 * Copyright (C) 2026 Emad Roshandel — GPL-3.0-or-later (see LICENSE)
 *
 * D3 owns the DOM of each chart it mounts (zoom and tooltips attach their own listeners).
 * The printed report keeps the static SVG versions in drawings.js.
 *
 * Every chart: axis titles with units, zoom along the chainage (wheel, drag, + / − buttons,
 * double-click or "Reset" to return), tooltips on hover AND on keyboard focus (Tab to a mark,
 * ← → to move between marks), a one-sentence summary for screen readers and a table of values.
 */
import { select, pointer, scaleLinear, axisBottom, axisLeft, area, line, bisector, max, min, zoom, zoomIdentity, format } from 'd3';

const W = 1000;
const reduceMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
const f1 = format(',.1f'), f2 = format(',.2f'), f0 = format(',.0f');
const nf = v => (Math.abs(v) < 10 ? f2(v) : Math.abs(v) < 100 ? f1(v) : f0(v));
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
let uid = 0;

// shared frame: svg, clip, axes, zoom along x, tooltip, tool buttons
function frame(host, { h, m, x0, x1, y0, y1, xTitle, yTitle, summary, onZoom }) {
  const id = 'ch' + (++uid);
  host.innerHTML = '';
  host.classList.add('d3chart');
  const tools = select(host).append('div').attr('class', 'chart-tools').attr('role', 'group').attr('aria-label', 'Zoom the chart');
  const svg = select(host).append('svg').attr('viewBox', `0 0 ${W} ${h}`).attr('class', 'chart d3')
    .attr('role', 'group').attr('aria-roledescription', 'chart').attr('aria-label', summary);
  select(host).append('p').attr('class', 'sr-only').text(summary);
  const tip = select(host).append('div').attr('class', 'chart-tip').attr('role', 'status').attr('aria-live', 'polite').attr('hidden', true);
  const iw = W - m.l - m.r, ih = h - m.t - m.b;
  svg.append('defs').html(`<clipPath id="${id}c"><rect x="0" y="-6" width="${iw}" height="${ih + 12}"/></clipPath>
    <pattern id="${id}h" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
      <rect width="6" height="6" fill="var(--bad)" fill-opacity=".55"/><line x1="0" y1="0" x2="0" y2="6" stroke="#fff" stroke-width="2" stroke-opacity=".7"/></pattern>`);
  const g = svg.append('g').attr('transform', `translate(${m.l},${m.t})`);
  const x = scaleLinear().domain([x0, x1]).range([0, iw]);
  const y = scaleLinear().domain([y0, y1]).nice().range([ih, 0]);
  g.append('g').attr('class', 'grid').call(axisLeft(y).ticks(5).tickSize(-iw).tickFormat(''));
  const gx = g.append('g').attr('class', 'axis').attr('transform', `translate(0,${ih})`);
  g.append('g').attr('class', 'axis').call(axisLeft(y).ticks(5).tickFormat(v => nf(v)));
  g.append('text').attr('class', 'axtitle').attr('x', iw).attr('y', ih + 34).attr('text-anchor', 'end').text(xTitle);
  g.append('text').attr('class', 'axtitle').attr('transform', 'rotate(-90)').attr('x', 0).attr('y', -m.l + 12).attr('text-anchor', 'end').text(yTitle);
  const plot = g.append('g').attr('clip-path', `url(#${id}c)`);
  const drawAxis = xs => gx.call(axisBottom(xs).ticks(8).tickFormat(v => f0(v)));
  drawAxis(x);
  let xz = x;
  const zb = zoom().scaleExtent([1, 40]).extent([[0, 0], [iw, ih]]).translateExtent([[0, 0], [iw, ih]])
    // the wheel zooms only with Ctrl or Shift held, so scrolling the page past a chart still scrolls
    .filter(ev => !ev.button && (ev.type !== 'wheel' || ev.ctrlKey || ev.shiftKey))
    .on('zoom', ev => { xz = ev.transform.rescaleX(x); drawAxis(xz); onZoom(xz); hideTip(); });
  svg.call(zb).on('dblclick.zoom', null).on('dblclick', () => reset());
  const step = k => svg.transition().duration(reduceMotion() ? 0 : 200).call(zb.scaleBy, k);
  const reset = () => svg.transition().duration(reduceMotion() ? 0 : 250).call(zb.transform, zoomIdentity);
  tools.append('button').attr('type', 'button').attr('class', 'btn2 sm').attr('aria-label', 'Zoom in').text('+').on('click', () => step(2));
  tools.append('button').attr('type', 'button').attr('class', 'btn2 sm').attr('aria-label', 'Zoom out').text('−').on('click', () => step(0.5));
  tools.append('button').attr('type', 'button').attr('class', 'btn2 sm').text('Reset').on('click', reset);
  tools.append('span').attr('class', 'note').text('Ctrl + wheel or the buttons zoom along the road, drag to move; hover or Tab to a mark for its values.');

  // tooltip placed in host coordinates from an SVG-unit point
  function showTip(html, sx, sy) {
    const r = host.getBoundingClientRect(), sr = svg.node().getBoundingClientRect();
    const k = sr.width / W;
    const px = sr.left - r.left + (m.l + sx) * k, py = sr.top - r.top + (m.t + sy) * k;
    tip.html(html).attr('hidden', null);
    const tw = tip.node().offsetWidth;
    tip.style('left', Math.max(4, Math.min(px + 12, r.width - tw - 4)) + 'px').style('top', Math.max(4, py - 12 - tip.node().offsetHeight) + 'px');
  }
  function hideTip() { tip.attr('hidden', true); }
  svg.on('mouseleave', hideTip);
  return { svg, g, plot, x, y, ih, iw, xz: () => xz, showTip, hideTip, host, tools };
}

// keyboard: ← → move focus between sibling marks
function arrowNav(sel) {
  sel.on('keydown', function (ev) {
    if (ev.key !== 'ArrowRight' && ev.key !== 'ArrowLeft') return;
    const all = [...this.parentNode.querySelectorAll('[tabindex="0"]')];
    const i = all.indexOf(this) + (ev.key === 'ArrowRight' ? 1 : -1);
    if (all[i]) { all[i].focus(); ev.preventDefault(); }
  });
}

function table(host, caption, cols, rows) {
  const d = select(host).append('details').attr('class', 'adv chart-table');
  d.append('summary').text('Table of values');
  d.append('table').attr('class', 't small').html(`<caption class="sr-only">${esc(caption)}</caption>
    <tr>${cols.map(c => `<th scope="col"${c.n ? ' class="n"' : ''}>${esc(c.t)}</th>`).join('')}</tr>
    ${rows.map(r => `<tr>${r.map((v, i) => `<td${cols[i].n ? ' class="n"' : ''}>${v}</td>`).join('')}</tr>`).join('')}`);
}

// ---------------------------------------------------------------------------
// average luminance / illuminance per span, against the requirement
// ---------------------------------------------------------------------------
export function spansChart(host, a, key, req, unit) {
  const sp = a.spans || [];
  if (!sp.length) { host.innerHTML = '<p class="note">No spans to show.</p>'; return; }
  const qty = key === 'L_avg' ? 'Average luminance' : 'Average illuminance';
  const vmax = Math.max(req || 0, max(sp, d => d[key] || 0)) * 1.15 || 1;
  const nFail = sp.filter(d => !d.checks.every(c => c.ok)).length;
  const lo = min(sp, d => d[key]), hi = max(sp, d => d[key]);
  const summary = `${qty} per span for ${a.name}: ${sp.length} spans between ${nf(lo)} and ${nf(hi)} ${unit}` +
    (req ? `, requirement ${nf(req)} ${unit}` : '') + `. ${nFail ? nFail + ' span' + (nFail > 1 ? 's do' : ' does') + ' not comply.' : 'Every span complies.'}`;
  const F = frame(host, { h: 230, m: { l: 66, r: 14, t: 14, b: 44 }, x0: sp[0].s0, x1: sp[sp.length - 1].s1, y0: 0, y1: vmax,
    xTitle: 'Chainage along the road (m)', yTitle: `${qty} (${unit})`, summary, onZoom: xs => draw(xs) });
  const ok = d => d.checks.every(c => c.ok);
  const hatch = F.svg.select('pattern').attr('id');
  const bars = F.plot.selectAll('rect.sbar').data(sp, d => d.s0).join('rect')
    .attr('class', d => 'sbar ' + (ok(d) ? 'ok' : 'bad'))
    .attr('fill', d => ok(d) ? 'var(--ok)' : `url(#${hatch})`)
    .attr('stroke', d => ok(d) ? 'none' : 'var(--bad-ink)')
    .attr('y', d => F.y(d[key] || 0)).attr('height', d => F.ih - F.y(d[key] || 0))
    .attr('tabindex', 0).attr('role', 'img')
    .attr('aria-label', d => `Span chainage ${f0(d.s0)} to ${f0(d.s1)} m: ${nf(d[key])} ${unit}, ${ok(d) ? 'complies' : 'does not comply: ' + d.checks.filter(c => !c.ok).map(c => c.name + ' (' + c.reason + ')').join(', ')}`);
  const tipHTML = d => `<b>Span ch ${f0(d.s0)}–${f0(d.s1)} m</b> <span class="verdict ${ok(d) ? 'ok' : 'bad'}">${ok(d) ? '✓ complies' : '✕ fails'}</span>
    <table>${d.checks.map(c => `<tr><td>${esc(c.name)}</td><td class="n"><b>${nf(c.value)}</b> ${esc(c.unit)}</td><td class="n">${c.op === '>=' ? '≥' : '≤'} ${nf(c.req)}</td><td>${c.ok ? '✓' : '✕ ' + esc(c.reason)}</td></tr>`).join('')}</table>`;
  const show = (ev, d) => F.showTip(tipHTML(d), (F.xz()(d.s0) + F.xz()(d.s1)) / 2, F.y(d[key] || 0));
  bars.on('mouseenter', show).on('focus', show).on('blur', F.hideTip);
  arrowNav(bars);
  if (req) {
    F.g.append('line').attr('class', 'req').attr('x1', 0).attr('x2', F.iw).attr('y1', F.y(req)).attr('y2', F.y(req));
    F.g.append('text').attr('class', 'reqlab').attr('x', F.iw - 4).attr('y', F.y(req) - 5).attr('text-anchor', 'end').text(`required ${nf(req)} ${unit}`);
  }
  // legend: colour AND pattern, so pass/fail does not rely on colour alone
  const lg = F.g.append('g').attr('class', 'lg').attr('transform', 'translate(8,-2)');
  lg.append('rect').attr('width', 12).attr('height', 10).attr('fill', 'var(--ok)');
  lg.append('text').attr('x', 17).attr('y', 9).text('complies');
  lg.append('rect').attr('x', 92).attr('width', 12).attr('height', 10).attr('fill', `url(#${hatch})`).attr('stroke', 'var(--bad-ink)');
  lg.append('text').attr('x', 109).attr('y', 9).text('does not comply');
  function draw(xs) { bars.attr('x', d => xs(d.s0) + 1).attr('width', d => Math.max(1, xs(d.s1) - xs(d.s0) - 2)); }
  draw(F.x);
  table(host, summary, [{ t: 'From ch (m)', n: 1 }, { t: 'To ch (m)', n: 1 }, { t: `${qty} (${unit})`, n: 1 }, { t: 'Result' }],
    sp.map(d => [f0(d.s0), f0(d.s1), nf(d[key]), ok(d) ? '✓ complies' : '✕ ' + esc(d.checks.filter(c => !c.ok).map(c => c.symbol).join(', '))]));
}

// ---------------------------------------------------------------------------
// vertical profile: road level, columns, and why each column stands where it does
// ---------------------------------------------------------------------------
export function profileChart(host, route) {
  const L = route.alignment.length;
  const zOf = profileFunction(route.profile, L);
  const poles = (route.poles || []).filter(p => p.H > 0).slice().sort((p, q) => p.s - q.s);
  const N = 400, pts = [];
  for (let i = 0; i <= N; i++) { const s = L * i / N; pts.push([s, zOf(s)]); }
  const zs = pts.map(p => p[1]).concat(poles.map(p => (p.z0 ?? zOf(p.s)) + p.H));
  const zmin = min(zs) - 2, zmax = max(zs) + 2;
  const grade = s => (zOf(Math.min(L, s + 0.5)) - zOf(Math.max(0, s - 0.5))) / 1 * 100;
  const curves = route.profile.curves || [];
  const summary = `Vertical profile, ${f0(L)} m long, road level ${f1(min(pts, p => p[1]))} to ${f1(max(pts, p => p[1]))} m` +
    (curves.length ? `, ${curves.map(c => (c.type === 'crest' ? 'crest' : 'sag') + ' at ch ' + f0(c.s)).join(', ')}` : '') +
    (poles.length ? `, ${poles.length} columns.` : '.');
  const F = frame(host, { h: 260, m: { l: 66, r: 14, t: 22, b: 44 }, x0: 0, x1: L, y0: zmin, y1: zmax,
    xTitle: 'Chainage along the road (m)', yTitle: 'Level (m)', summary, onZoom: xs => draw(xs) });
  const ground = F.plot.append('path').attr('class', 'ground');
  const road = F.plot.append('path').attr('class', 'roadline');
  // vertical-curve labels sit outside the clip, above the plot
  const cl = F.g.selectAll('g.curve').data(curves).join('g').attr('class', 'curve');
  cl.append('line').attr('class', 'curvetick').attr('y1', -3).attr('y2', F.ih);
  cl.append('text').attr('class', 'tag small').attr('text-anchor', 'middle').attr('y', -7)
    .text(c => `${c.type === 'crest' ? 'crest' : 'sag'} ${f1(c.g1)} % → ${f1(c.g2)} %`);
  const pg = F.plot.selectAll('g.pole').data(poles).join('g').attr('class', 'pole').attr('tabindex', 0).attr('role', 'img')
    .attr('aria-label', (p, i) => `Column ${i + 1} at chainage ${f1(p.s)} m, height ${f1(p.H)} m: ${p.reason || 'regular spacing'}`);
  pg.append('line').attr('class', 'mast');
  pg.append('circle').attr('r', 4).attr('class', 'head');
  pg.append('rect').attr('class', 'hit').attr('width', 14).attr('x', -7);    // wider target than the thin mast
  const tipPole = (p, i) => `<b>Column ${i + 1}</b> · ch ${f1(p.s)} m<br>Height ${f1(p.H)} m${p.side !== undefined ? ' · side ' + (p.side > 0 ? 'A' : 'B') : ''}<br>
    <span class="why">${esc(p.reason || 'regular spacing')}</span>`;
  pg.on('mouseenter focus', function (ev, p) { const i = poles.indexOf(p); F.showTip(tipPole(p, i), F.xz()(p.s), F.y((p.z0 ?? zOf(p.s)) + p.H)); })
    .on('blur', F.hideTip);
  arrowNav(pg);
  // crosshair: chainage, level and grade anywhere on the road
  const cross = F.plot.append('g').attr('class', 'cross').attr('hidden', true);
  cross.append('line').attr('y1', 0).attr('y2', F.ih);
  cross.append('circle').attr('r', 3.5);
  const bis = bisector(p => p[0]).center;
  F.svg.on('pointermove', function (ev) {
    if (ev.target.closest && ev.target.closest('g.pole')) return;
    const [px] = pointer(ev, F.g.node());
    if (px < 0 || px > F.iw) { cross.attr('hidden', true); return; }
    const s = F.xz().invert(px), z = zOf(s);
    cross.attr('hidden', null).attr('transform', `translate(${F.xz()(s)},0)`);
    cross.select('circle').attr('cy', F.y(z));
    F.showTip(`ch <b>${f1(s)}</b> m · level <b>${f2(z)}</b> m · grade <b>${f1(grade(s))}</b> %`, F.xz()(s), F.y(z));
  }).on('pointerleave', () => cross.attr('hidden', true));
  function draw(xs) {
    ground.attr('d', area().x(p => xs(p[0])).y0(F.ih).y1(p => F.y(p[1]))(pts));
    road.attr('d', line().x(p => xs(p[0])).y(p => F.y(p[1]))(pts));
    cl.attr('transform', c => `translate(${xs(c.s)},0)`).attr('display', c => (xs(c.s) < 0 || xs(c.s) > F.iw ? 'none' : null));     // above the plot, clear of the columns
    pg.attr('transform', p => `translate(${xs(p.s)},0)`);
    pg.select('line').attr('y1', p => F.y(p.z0 ?? zOf(p.s))).attr('y2', p => F.y((p.z0 ?? zOf(p.s)) + p.H));
    pg.select('circle').attr('cy', p => F.y((p.z0 ?? zOf(p.s)) + p.H));
    pg.select('rect').attr('y', p => F.y((p.z0 ?? zOf(p.s)) + p.H) - 7).attr('height', p => F.y(p.z0 ?? zOf(p.s)) - F.y((p.z0 ?? zOf(p.s)) + p.H) + 7);
  }
  draw(F.x);
  if (poles.length) table(host, summary, [{ t: 'Column' }, { t: 'Chainage (m)', n: 1 }, { t: 'Height (m)', n: 1 }, { t: 'Why here' }],
    poles.map((p, i) => [i + 1, f1(p.s), f1(p.H), esc(p.reason || 'regular spacing')]));
}

// level along the road from the PVIs, with parabolic vertical curves of length Lc centred on each PVI
export function profileFunction(profile, L) {
  const pv = (profile && profile.pvis && profile.pvis.length) ? profile.pvis.slice().sort((a, b) => a[0] - b[0]) : [[0, 0], [L, 0]];
  const lin = s => {
    if (pv.length === 1) return pv[0][1];
    let i = 0;
    while (i < pv.length - 2 && s > pv[i + 1][0]) i++;
    const [s0, z0] = pv[i], [s1, z1] = pv[i + 1];
    return z0 + (z1 - z0) * (s - s0) / ((s1 - s0) || 1);
  };
  const g = i => (pv[i + 1][1] - pv[i][1]) / ((pv[i + 1][0] - pv[i][0]) || 1);
  return s => {
    for (let i = 1; i < pv.length - 1; i++) {
      const Lc = pv[i][2] || 0;
      if (Lc > 0 && Math.abs(s - pv[i][0]) < Lc / 2) {
        const sb = pv[i][0] - Lc / 2, zb = pv[i][1] - g(i - 1) * Lc / 2, t = s - sb;
        return zb + g(i - 1) * t + (g(i) - g(i - 1)) * t * t / (2 * Lc);
      }
    }
    return lin(s);
  };
}
