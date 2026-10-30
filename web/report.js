/* Street Lighting — design report (English / Persian).
 * Copyright (C) 2026 Emad Roshandel — GPL-3.0-or-later (see LICENSE)
 *
 * The report is assembled in the browser from the results already on screen,
 * shown in a full-window frame, and printed or saved as PDF from there.
 */
import { esc, fmt, legendSVG, download } from './util.js';
import * as D from './drawings.js';

const FA = {
  'Street lighting design report': 'گزارش طراحی روشنایی معابر',
  'Project': 'پروژه', 'Client': 'کارفرما', 'Prepared by': 'تهیه‌کننده', 'Date': 'تاریخ', 'Standard': 'استاندارد',
  'Summary': 'خلاصه', 'Design': 'طرح', 'Arrangement': 'آرایش', 'Mounting height': 'ارتفاع نصب', 'Spacing': 'فاصلهٔ پایه‌ها',
  'Arm length': 'طول بازو', 'Tilt': 'زاویهٔ شیب', 'Light output': 'شار نوری (درصد)', 'Maintenance factor': 'ضریب نگهداری',
  'Luminaire': 'چراغ', 'Cross-section': 'مقطع عرضی', 'Lighting results': 'نتایج روشنایی', 'Criterion': 'معیار',
  'Value': 'مقدار', 'Required': 'الزام', 'Result': 'نتیجه', 'Reason': 'دلیل', 'pass': 'قبول', 'fail': 'رد', 'note': 'توجه',
  'Isolux contours': 'منحنی‌های هم‌روشنایی (لوکس)', 'Isoluminance contours': 'منحنی‌های هم‌درخشندگی (cd/m²)',
  'Route': 'مسیر', 'Topology': 'شرایط مسیر', 'Route plan': 'پلان مسیر', 'Vertical profile': 'نیم‌رخ طولی',
  'Spans': 'دهانه‌ها', 'Column schedule': 'جدول پایه‌ها', 'Views': 'نماها', 'Electrical': 'تأسیسات برقی',
  'Feeder pillars and circuits': 'تابلوها و مدارها', 'Single-line diagram': 'نقشهٔ تک‌خطی', 'Columns and foundations': 'پایه‌ها و فونداسیون',
  'Energy and cost': 'انرژی و هزینه', 'Method and references': 'روش و مراجع', 'Assumptions and limits': 'فرض‌ها و محدودیت‌ها',
  'Complies': 'منطبق است', 'Does not comply': 'منطبق نیست', 'Print / save as PDF': 'چاپ / ذخیره PDF', 'Download HTML': 'دریافت HTML', 'Close': 'بستن',
  'Area': 'ناحیه', 'Class': 'کلاس', 'Observer': 'ناظر', 'lane': 'خط', 'Night view': 'نمای شب', 'Day view': 'نمای روز',
  'Chainage': 'کیلومتراژ', 'Height': 'ارتفاع', 'Why here': 'دلیل جانمایی', 'Feeder': 'فیدر', 'Cable': 'کابل', 'Length': 'طول',
  'Luminaires': 'چراغ‌ها', 'Voltage drop': 'افت ولتاژ', 'Loop impedance': 'امپدانس حلقه', 'Base': 'پایه', 'Use': 'بهره‌برداری',
  'Foundation': 'فونداسیون', 'Deflection': 'تغییر مکان', 'Light distribution': 'منحنی پخش نور', 'Installed power': 'توان نصب‌شده',
  'Energy per year': 'انرژی سالانه', 'Cost per year': 'هزینهٔ سالانه', 'CO₂ per year': 'CO₂ سالانه',
  'Refinement': 'اصلاح تدریجی', 'Round': 'مرحله', 'Failing spans': 'دهانه‌های ناموفق',
};
const ADVICE_FA = {
  'maintained luminance meets the class minimum': 'درخشندگی نگهداری‌شده حداقل کلاس را تأمین می‌کند',
  'darkest point is bright enough relative to the average': 'تاریک‌ترین نقطه نسبت به میانگین به اندازهٔ کافی روشن است',
  'bright/dark pattern along the lane is acceptable': 'الگوی روشن و تاریک در طول خط قابل قبول است',
  'disability glare is limited': 'خیرگی ناتوان‌کننده محدود است',
  'the road surroundings are lit': 'حاشیهٔ معبر روشن است',
  'illuminance meets the class': 'روشنایی الزام کلاس را تأمین می‌کند', 'no dark spots': 'نقطهٔ تاریک وجود ندارد',
  'not over-lit (Table 3 note a)': 'بیش‌روشنایی وجود ندارد', 'even illumination': 'روشنایی یکنواخت است',
};

export function openReport(ctx) {
  const html = build(ctx);
  let ov = document.getElementById('reportOverlay');
  if (!ov) {
    ov = document.createElement('div');
    ov.id = 'reportOverlay';
    ov.style.cssText = 'position:fixed;inset:0;z-index:60;background:rgba(14,22,38,.8);display:flex;flex-direction:column';
    document.body.appendChild(ov);
  }
  const t = (en) => tr(en, ctx.lang);
  // a modal dialog: focus moves in, stays in, Escape closes, focus returns to the button that opened it
  const opener = document.activeElement;
  ov.setAttribute('role', 'dialog');
  ov.setAttribute('aria-modal', 'true');
  ov.setAttribute('aria-label', 'Report');
  ov.innerHTML = `<div style="display:flex;gap:8px;padding:8px 12px;background:#0e1626">
    <button class="btn" id="repPrint">${t('Print / save as PDF')}</button>
    <button class="btn2" id="repHtml">${t('Download HTML')}</button><span style="flex:1"></span>
    <button class="btn2" id="repClose">${t('Close')}</button></div>
    <iframe id="repFrame" title="Report" style="flex:1;border:0;background:#fff"></iframe>`;
  const fr = document.getElementById('repFrame');
  fr.srcdoc = html;
  const close = () => { ov.remove(); document.removeEventListener('keydown', onKey, true); if (opener && opener.focus) opener.focus(); };
  const onKey = e => {
    if (e.key === 'Escape') { e.preventDefault(); close(); return; }
    if (e.key === 'Tab') {                      // keep Tab inside the dialog
      const f = [...ov.querySelectorAll('button, iframe')];
      const i = f.indexOf(document.activeElement);
      if (e.shiftKey && i <= 0) { e.preventDefault(); f[f.length - 1].focus(); }
      else if (!e.shiftKey && i === f.length - 1) { e.preventDefault(); f[0].focus(); }
    }
  };
  document.addEventListener('keydown', onKey, true);
  document.getElementById('repPrint').onclick = () => fr.contentWindow.print();
  document.getElementById('repHtml').onclick = () => download((ctx.P.name || 'report').replace(/\s+/g, '_') + '_report.html', html, 'text/html');
  document.getElementById('repClose').onclick = close;
  document.getElementById('repPrint').focus();
}

function tr(en, lang) {
  if (lang === 'fa') return FA[en] || en;
  if (lang === 'both') return FA[en] ? `${en} <span class="fa">${FA[en]}</span>` : en;
  return en;
}

function build({ P, R, LUM, META, imgs, energy, lang }) {
  const t = (en) => tr(en, lang);
  const rtl = lang === 'fa';
  const c = R.sel, e = R.eval;
  const lum = LUM[c.phot] || {};
  const std = (P.standard || 'EN13201') === 'RP8' ? 'ANSI/IESNA RP-8-00 (R2005)' : 'EN 13201-2:2015 / EN 13201-3:2015 / EN 13201-5:2015';
  const today = new Date().toISOString().slice(0, 10);
  const ok = e.ok && (!R.route || R.route.ok);
  const sec = [];
  const H = (n, txt) => `<h${n}>${t(txt)}</h${n}>`;
  const reason = (r) => lang === 'en' ? esc(r) : (ADVICE_FA[r] ? (lang === 'both' ? esc(r) + ' — <span class="fa">' + ADVICE_FA[r] + '</span>' : ADVICE_FA[r]) : esc(r));

  sec.push(`<section class="cover">
    <div class="band"></div>
    <h1>${t('Street lighting design report')}</h1>
    <table class="kv"><tr><th>${t('Project')}</th><td>${esc(P.name || '')}</td></tr>
    <tr><th>${t('Client')}</th><td>${esc(P.report_for || '')}</td></tr>
    <tr><th>${t('Prepared by')}</th><td>${esc(P.report_by || '')}</td></tr>
    <tr><th>${t('Date')}</th><td>${today}</td></tr>
    <tr><th>${t('Standard')}</th><td>${std}</td></tr></table>
    <p class="verdict ${ok ? 'ok' : 'bad'}">${ok ? t('Complies') : t('Does not comply')}</p>
    ${imgs.night ? `<img class="hero" src="${imgs.night}" alt="night view">` : ''}
  </section>`);

  sec.push(`<section>${H(2, 'Summary')}
    <table class="kv"><tr><th>${t('Arrangement')}</th><td>${esc(c.label)}</td></tr>
    <tr><th>${t('Luminaire')}</th><td>${esc(P.luminaires[c.phot]?.name || lum.name || '')}${P.luminaires[c.phot]?.source === 'generic' ? ' (generic optic — indicative)' : ''}</td></tr>
    <tr><th>${t('Mounting height')}</th><td>${fmt(c.H, 1)} m</td></tr>
    <tr><th>${t('Spacing')}</th><td>${fmt(c.S, 2)} m${R.route ? ` (route: ${R.route.result.n_poles} columns over ${fmt(R.route.result.length, 0)} m)` : ''}</td></tr>
    <tr><th>${t('Arm length')}</th><td>${fmt(c.overhang, 1)} m</td></tr><tr><th>${t('Tilt')}</th><td>${fmt(c.tilt, 0)}°</td></tr>
    <tr><th>${t('Light output')}</th><td>${fmt(c.f * 100, 0)} % (${fmt(lum.luminaire_flux * c.f, 0)} lm, ${fmt(lum.power * (0.08 + 0.92 * c.f), 0)} W)</td></tr>
    <tr><th>${t('Maintenance factor')}</th><td>${fmt(e.fM, 3)}</td></tr>
    <tr><th>Intensity / glare class</th><td>${e.gstar.cls} / ${e.glare.cls}</td></tr></table></section>`);

  sec.push(`<section>${H(2, 'Luminaire')}<div class="two"><div>${D.polarSVG(lum.polar, 300)}</div><table class="kv small">
    <tr><th>Lamp / luminaire flux</th><td>${fmt(lum.lamp_flux, 0)} / ${fmt(lum.luminaire_flux, 0)} lm</td></tr>
    <tr><th>Power · efficacy</th><td>${fmt(lum.power, 1)} W · ${fmt(lum.efficacy, 0)} lm/W</td></tr>
    <tr><th>LOR · ULOR</th><td>${fmt(lum.lor * 100, 1)} % · ${fmt(lum.ulor * 100, 2)} %</td></tr>
    <tr><th>Peak intensity</th><td>${fmt(lum.imax, 0)} cd (C${fmt(lum.imax_C, 0)}, γ${fmt(lum.imax_gamma, 0)})</td></tr>
    <tr><th>CCT · CRI</th><td>${fmt(lum.cct, 0)} K · ${fmt(lum.cri, 0)}</td></tr>
    <tr><th>Installed G* class (tilt ${fmt(c.tilt, 0)}°)</th><td>${e.gstar.cls}: ${fmt(e.gstar.i70, 0)} / ${fmt(e.gstar.i80, 0)} / ${fmt(e.gstar.i90, 0)} cd/klm at 70/80/90°</td></tr>
    <tr><th>Source</th><td>${esc((lum.notes || []).join(' '))}</td></tr></table></div></section>`);

  sec.push(`<section>${H(2, 'Cross-section')}${D.crossSection(P.section.elements, c.rows, { trees: (P.route.features || {}).tree_lines || [] })}</section>`);

  const crit = (a) => `<table class="grid"><tr><th>${t('Criterion')}</th><th>${t('Value')}</th><th>${t('Required')}</th><th>${t('Result')}</th><th>${t('Reason')}</th></tr>
    ${(a.checks || []).map(k => `<tr><td>${esc(k.name)} ${esc(k.symbol || '')}</td><td class="n">${fmt(k.value, k.unit === '%' ? 1 : 2)} ${esc(k.unit || '')}</td>
      <td class="n">${k.op === '>=' ? '≥' : '≤'} ${fmt(k.req, 2)}</td><td class="${k.ok ? (k.met === false ? 'adv' : 'okc') : 'badc'}">${t(k.ok ? (k.met === false ? 'note' : 'pass') : 'fail')}</td><td>${reason(k.reason)}</td></tr>`).join('')}</table>`;
  sec.push(`<section>${H(2, 'Lighting results')}<p class="small">Calculated to EN 13201-3:2015 on the standard grid for one span (field of calculation between two luminaires of the reference row); maintained values with f<sub>M</sub> = ${fmt(e.fM, 3)}.</p>
    ${e.areas.filter(a => a.cls).map(a => `<h3>${esc(a.name)} — ${a.cls}</h3>${crit(a)}
      ${a.observers ? `<table class="grid small"><tr><th>${t('Observer')}</th><th>L̄ cd/m²</th><th>Uo</th><th>Ul</th>${a.observers.some(o => o.TI != null) ? '<th>fTI %</th>' : ''}</tr>${a.observers.map(o => `<tr><td>${t('lane')} ${o.lane}</td><td class="n">${fmt(o.L_avg, 2)}</td><td class="n">${fmt(o.U0, 2)}</td><td class="n">${fmt(o.Ul, 2)}</td>${o.TI != null ? `<td class="n">${fmt(o.TI, 1)}</td>` : ''}</tr>`).join('')}</table>` : ''}
      <p class="small">Ē ${fmt(a.E_avg, 2)} lx · E<sub>min</sub> ${fmt(a.E_min, 2)} lx · E<sub>max</sub> ${fmt(a.E_max, 2)} lx · U<sub>o</sub>(E) ${fmt(a.U0_E, 2)}${a.TI !== undefined ? ` · f<sub>TI</sub> ${fmt(a.TI, 1)} %` : ''}</p>`).join('')}</section>`);

  for (const q of ['E', 'L']) {
    if (q === 'L' && !e.display.L) continue;
    const out = D.sectionPlan(P.section, c, e, { quantity: q, scale: 'classic', points: true });
    sec.push(`<section>${H(2, q === 'E' ? 'Isolux contours' : 'Isoluminance contours')}${out.svg}${legendSVG(out.vmax, out.unit, 'classic', [], 320)}</section>`);
  }

  if (R.route) {
    const rr = R.route;
    sec.push(`<section>${H(2, 'Route')}${H(3, 'Topology')}<ul>${rr.topology.map(x => `<li>${esc(x.text)}</li>`).join('') || '<li>Straight and level.</li>'}</ul>
      <table class="grid">${rr.checks.map(k => `<tr><td>${esc(k.area)} — ${esc(k.name)}</td><td class="n">${typeof k.value === 'number' && k.value % 1 ? fmt(k.value, 1) : k.value}</td><td class="n">${k.name.startsWith('Threshold') ? '≤ ' + k.req + ' %' : 'of ' + k.req}</td><td class="${k.ok ? 'okc' : 'badc'}">${t(k.ok ? 'pass' : 'fail')}</td><td>${esc(k.reason)}</td></tr>`).join('')}</table>
      ${rr.history.length > 1 ? `${H(3, 'Refinement')}<table class="grid small"><tr><th>${t('Round')}</th><th>${t('Luminaires')}</th><th>${t('Failing spans')}</th></tr>${rr.history.map(h => `<tr><td>${h.iteration}</td><td class="n">${h.n_poles}</td><td class="n">${h.n_fail}</td></tr>`).join('')}</table>` : ''}</section>`);
    for (const q of ['E', 'L']) {
      const out = D.routePlan(rr, { quantity: q, scale: 'classic', electrical: q === 'E' ? R.elec : null, ids: true });
      sec.push(`<section>${H(2, 'Route plan')} — ${q === 'E' ? t('Isolux contours') : t('Isoluminance contours')}${out.svg}${legendSVG(out.vmax, out.unit, 'classic', [], 320)}</section>`);
    }
    sec.push(`<section>${H(2, 'Vertical profile')}${D.profileSVG(rr)}</section>`);
    sec.push(`<section>${H(2, 'Spans')}${rr.result.areas.map(a => `<h3>${esc(a.name)} — ${a.cls}</h3>
      ${D.spansChart(a, a.L_avg !== undefined ? 'L_avg' : 'E_avg', a.spans[0]?.checks?.[0]?.req, a.L_avg !== undefined ? 'cd/m²' : 'lx')}
      <table class="grid small"><tr><th>${t('Chainage')}</th><th>Ē lx</th><th>U<sub>o</sub>(E)</th>${a.L_avg !== undefined ? '<th>L̄</th><th>Uo</th><th>Ul</th>' : ''}<th>${t('Result')}</th></tr>
      ${a.spans.map(s => `<tr><td>${fmt(s.s0, 0)}–${fmt(s.s1, 0)}</td><td class="n">${fmt(s.E_avg, 2)}</td><td class="n">${fmt(s.U0_E, 2)}</td>${a.L_avg !== undefined ? `<td class="n">${fmt(s.L_avg, 2)}</td><td class="n">${fmt(s.U0_L, 2)}</td><td class="n">${s.Ul_applies ? fmt(s.Ul, 2) : '–'}</td>` : ''}<td class="${s.ok ? 'okc' : 'badc'}">${t(s.ok ? 'pass' : 'fail')}${s.why && s.why.length ? ' (' + s.why.join(', ') + ')' : ''}</td></tr>`).join('')}</table>`).join('')}</section>`);
    sec.push(`<section>${H(2, 'Column schedule')}<table class="grid small"><tr><th>Id</th><th>${t('Chainage')}</th><th>x</th><th>y</th><th>z</th><th>${t('Height')}</th><th>${t('Arm length')}</th><th>${t('Tilt')}</th><th>${t('Light output')}</th><th>${t('Why here')}</th></tr>
      ${rr.poles.map(p => `<tr><td>${p.id}</td><td class="n">${fmt(p.s, 1)}</td><td class="n">${fmt(p.x, 2)}</td><td class="n">${fmt(p.yw, 2)}</td><td class="n">${fmt(p.z0, 2)}</td><td class="n">${fmt(p.H, 1)}</td><td class="n">${fmt(p.overhang, 1)}</td><td class="n">${fmt(p.tilt, 0)}°</td><td class="n">${fmt(p.flux * 100, 0)} %</td><td>${esc(p.reason)}</td></tr>`).join('')}</table></section>`);
  }
  if (imgs.night || imgs.day) sec.push(`<section>${H(2, 'Views')}<div class="two">${imgs.night ? `<figure><img src="${imgs.night}"><figcaption>${t('Night view')}</figcaption></figure>` : ''}${imgs.day ? `<figure><img src="${imgs.day}"><figcaption>${t('Night view')} — driver's eye</figcaption></figure>` : ''}</div></section>`);

  if (R.elec) {
    const el = R.elec, cf = el.config;
    sec.push(`<section>${H(2, 'Electrical')}<p class="small">${esc(cf.system)} ${fmt(cf.U0, 0)}/${fmt(cf.Un, 0)} V · ${esc(cf.material)} ${esc(cf.insulation)} · method ${esc(cf.method)} · ${fmt(cf.t_ground, 0)} °C ground · ${fmt(cf.rho_soil, 1)} K·m/W · max ΔU ${fmt(cf.du_max, 1)} % · device ${esc(cf.device)} · Z<sub>e</sub> ${fmt(cf.Ze, 2)} Ω</p>
      ${H(3, 'Feeder pillars and circuits')}<table class="grid small"><tr><th>${t('Feeder')}</th><th>${t('Luminaires')}</th><th>${t('Cable')}</th><th>${t('Length')}</th><th>I<sub>b</sub> A</th><th>I<sub>n</sub> A</th><th>I<sub>z</sub> A</th><th>${t('Voltage drop')} %</th><th>${t('Loop impedance')} Ω</th><th>${t('Result')}</th></tr>
      ${el.feeders.map(f => `<tr><td>${f.id}</td><td class="n">${f.poles.length}</td><td class="n">5×${f.size} mm²</td><td class="n">${fmt(f.length, 0)} m</td><td class="n">${fmt(f.Ib, 1)}</td><td class="n">${f.In}</td><td class="n">${fmt(f.Iz, 0)}</td><td class="n">${fmt(f.du_max, 2)}</td><td class="n">${fmt(f.Zs, 2)} ≤ ${fmt(f.Zs_max, 2)}</td><td class="${f.ok ? 'okc' : 'badc'}">${t(f.ok ? 'pass' : 'fail')}${f.msgs.length ? ' — ' + f.msgs.map(esc).join('; ') : ''}</td></tr>`).join('')}</table>
      ${H(3, 'Single-line diagram')}${D.sldSVG(el)}
      ${(el.installation_notes || []).length ? `${H(3, 'Site requirements (IEC 60364-7-714)')}<ul class="small">${el.installation_notes.map(n => `<li>${esc(n)}</li>`).join('')}</ul>` : ''}</section>`);
  }
  if (R.struct && R.struct.length) {
    sec.push(`<section>${H(2, 'Columns and foundations')}<div class="two">${R.struct.map(k => {
      const cc = k.r.column, f = k.r.foundation;
      return `<div>${D.columnSVG(k.r, k.H, k.overhang)}<table class="kv small"><tr><th>q(10) / q(h)</th><td>${fmt(cc.q10, 0)} / ${fmt(cc.q_h, 0)} Pa</td></tr>
        <tr><th>T, β, δ</th><td>${fmt(cc.T, 2)} s, ${fmt(cc.beta, 2)}, ${fmt(cc.delta, 2)}</td></tr>
        <tr><th>${t('Base')}</th><td>Ø${fmt(cc.D_base * 1000, 0)}×${fmt(cc.t * 1000, 0)} mm ${esc(cc.grade)}, M<sub>Ed</sub> ${fmt(cc.M_design / 1000, 2)} kNm</td></tr>
        <tr><th>${t('Use')}</th><td>${fmt(cc.util * 100, 0)} % (base ${fmt(cc.util_base * 100, 0)} %, door ${fmt(cc.util_door * 100, 0)} %; class ${esc(cc.load_class)}, terrain ${esc(cc.terrain)}, φ<sub>1</sub> ${fmt(cc.phi1, 2)})</td></tr><tr><th>${t('Deflection')}</th><td>${fmt(cc.deflection * 1000, 0)} / ${fmt(cc.defl_limit * 1000, 0)} mm</td></tr>
        <tr><th>${t('Foundation')}</th><td>Ø${fmt(f.diameter, 2)} × ${fmt(f.depth, 2)} m — ${esc(f.method)}${(f.alternatives || []).length ? ' (' + f.alternatives.map(a => esc(a.method.split(' (')[0]) + ' ' + fmt(a.depth, 2) + ' m').join('; ') + ')' : ''}</td></tr></table></div>`; }).join('')}</div>
      <p class="small">EN 40-3-1:2013 loads (C<sub>s</sub> = √0.92, β of 5.2.4, c<sub>e</sub>(z) of Table 2/3, shape coefficients of Figure 3); EN 40-3-3:2013 resistance of the closed section and of an unreinforced door opening, interaction Formulae (10) and (11), deflection Table 4.</p></section>`);
  }
  if (energy) {
    sec.push(`<section>${H(2, 'Energy and cost')}<table class="kv"><tr><th>PDI D<sub>P</sub></th><td>${fmt(energy.PDI * 1000, 2)} mW/(lx·m²)</td></tr>
      <tr><th>AECI D<sub>E</sub></th><td>${fmt(energy.AECI / 1000, 3)} kWh/(m²·yr)</td></tr>
      <tr><th>${t('Installed power')}</th><td>${fmt(energy.W / 1000, 2)} kW</td></tr><tr><th>${t('Energy per year')}</th><td>${fmt(energy.kWh, 0)} kWh</td></tr>
      <tr><th>${t('Cost per year')}</th><td>${fmt(energy.cost, 0)} ${esc((P.costs || {}).currency || '')}</td></tr><tr><th>${t('CO₂ per year')}</th><td>${fmt(energy.co2, 2)} t</td></tr></table>
      <p class="small">EN 13201-5:2015 Formulae (1) and (3), for ${esc(energy.scope)}.</p></section>`);
  }
  sec.push(`<section>${H(2, 'Method and references')}<ul class="small">
    <li>Lighting classes: EN 13201-2:2015 Tables 1–6 and Annex C${(P.standard || '') === 'RP8' ? '; ANSI/IESNA RP-8-00 Tables 2, 3, 5–7' : ''}; class selection after CEN/TR 13201-1:2014.</li>
    <li>Calculation: EN 13201-3:2015 (CIE 140:2019) — I-table and r-table bilinear interpolation, luminance with observers 60 m before the field in every lane, threshold increment (Formulae 35–40), edge illuminance ratio. Road reflection: standard CIE r-tables (${esc([...new Set(P.section.elements.filter(x => x.kind === 'carriageway').map(x => x.surface || 'R3'))].join(', '))}).</li>
    <li>Route: point-by-point calculation on the real alignment, grade and cross-fall; observers fixed 60 m before each span; tree crowns attenuate light by Beer–Lambert (not part of the EN 13201-3 convention, reported in addition).</li>
    <li>Energy: EN 13201-5:2015. Maintenance: CIE 154:2003.</li>
    <li>Electrical: IEC 60364-5-52:2009 (Tables B.52.2–B.52.5, B.52.15–B.52.19, Annex G), IEC 60364-4-41, IEC 60364-4-43, IEC 60228.</li>
    <li>Columns: EN 40-3-1:2013 wind loads with EN 1991-1-4:2005 exposure; foundation by Broms' method.</li></ul>
    ${H(3, 'Assumptions and limits')}<ul class="small">
    <li>Photometry: ${esc((lum.notes || []).join(' '))}</li>
    <li>Column and foundation sizes are a pre-design; the supplier's EN 40-3-3 verification governs.</li>
    <li>Fault-loop and short-circuit checks use the supply impedance entered; confirm with the network operator.</li></ul>
    <p class="small">Street Lighting ${esc(META.version)} — GPL-3.0-or-later.</p></section>`);

  return `<!doctype html><html lang="${rtl ? 'fa' : 'en'}" dir="${rtl ? 'rtl' : 'ltr'}"><head><meta charset="utf-8"><title>${esc(P.name || 'Street lighting')} — report</title>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;600&family=Vazirmatn:wght@400;600&display=swap">
  <style>
  body{font:11pt/1.45 Barlow,'Segoe UI',sans-serif;color:#17212b;margin:0;padding:18mm 16mm;${rtl ? "font-family:Vazirmatn,Tahoma,sans-serif;" : ''}}
  h1{font-size:26pt;margin:40mm 0 8mm} h2{font-size:16pt;border-bottom:2px solid #f2c230;padding-bottom:3px;margin:0 0 10px} h3{font-size:12.5pt;margin:14px 0 6px}
  section{page-break-after:always;margin-bottom:12mm} section:last-child{page-break-after:auto}
  .band{height:10mm;background:#0e1626;margin:-18mm -16mm 0} .hero{width:100%;margin-top:12mm;border-radius:4px}
  table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums} .kv th{text-align:${rtl ? 'right' : 'left'};width:36%;color:#4b5865;font-weight:600;padding:3px 8px 3px 0;vertical-align:top} .kv td{padding:3px 0}
  .grid th,.grid td{border:1px solid #d3dade;padding:3px 6px;font-size:9.5pt;text-align:${rtl ? 'right' : 'left'}} .grid th{background:#eef2f4} .n{text-align:right!important}
  .okc{color:#2e8b57;font-weight:600} .badc{color:#c8412c;font-weight:600} .adv{color:#b7791f;font-weight:600}
  .verdict{display:inline-block;padding:6px 16px;border-radius:999px;font-weight:600;font-size:13pt} .verdict.ok{background:#dff0e6;color:#2e8b57} .verdict.bad{background:#f8e1dc;color:#c8412c}
  .small{font-size:9.5pt} svg{max-width:100%;height:auto} .two{display:grid;grid-template-columns:1fr 1fr;gap:12px} figure{margin:0} figure img{width:100%} figcaption{font-size:9pt;color:#4b5865}
  .fa{font-family:Vazirmatn,Tahoma,sans-serif;direction:rtl;unicode-bidi:embed;color:#4b5865;font-weight:400}
  :root{--ink:#17212b;--ink2:#4b5865;--line:#c8d0d4;--ground:#dcd6c8;--accent:#f2c230;--accent-ink:#1f5f9e;--ok:#2e8b57;--bad:#c8412c;--ok-bg:#dff0e6;--bad-bg:#f8e1dc}
  svg .dim{font:500 11px Barlow,sans-serif;fill:#17212b} svg .dim.acc{fill:#1f5f9e} svg .lbl{font:500 11px Barlow,sans-serif;fill:#4b5865} svg .iso{font:600 9.5px Barlow,sans-serif;fill:#111}
  svg .iso.small{font-size:7.5px} svg .tag{font:500 11px Barlow,sans-serif;fill:#17212b} svg .tag.small{font-size:9.5px;fill:#4b5865} svg .h{font:600 14px Barlow,sans-serif}
  .legend{color:#17212b} svg.legendsvg{max-width:340px;display:block;margin:4px 0 0} .two .kv th{width:48%} @page{size:A4;margin:0} @media print{body{padding:14mm 12mm}}
  </style></head><body>${sec.join('')}</body></html>`;
}
