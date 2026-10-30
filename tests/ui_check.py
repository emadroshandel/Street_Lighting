"""Browser check of the Street Lighting interface (Playwright).

Copyright (C) 2026 Emad Roshandel — GPL-3.0-or-later (see LICENSE)

Runs the whole design in a real browser and checks what a user would notice: page errors, the 3D
view (draw calls, rendering only on demand), the interactive charts, keyboard access, the help
badges, Undo, the report dialog, contrast and labels, and a phone-width layout.

    python -m pip install playwright && python -m playwright install chromium   (once)
    python tests/ui_check.py              # starts the local server itself
    python tests/ui_check.py --shots out  # also saves screenshots

Not part of the unit tests (it needs a browser); run it before a release.
Exit code 0 when every check passes.
"""
import argparse
import os
import socket
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# contrast / small text / labels / target size, evaluated in the page
AUDIT_JS = r"""() => {
  const parse = c => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(',').map(Number); return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 }; };
  const lum = ({ r, g, b }) => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const ratio = (a, b) => { const A = lum(a), B = lum(b); return (Math.max(A, B) + 0.05) / (Math.min(A, B) + 0.05); };
  const bgOf = el => { const st = []; for (let e = el; e; e = e.parentElement) { const c = parse(getComputedStyle(e).backgroundColor); if (c && c.a > 0) { st.push(c); if (c.a >= 0.99) break; } } let b = { r: 255, g: 255, b: 255 }; for (let i = st.length - 1; i >= 0; i--) { const c = st[i]; b = { r: c.r * c.a + b.r * (1 - c.a), g: c.g * c.a + b.g * (1 - c.a), b: c.b * c.a + b.b * (1 - c.a) }; } return b; };
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && e.offsetParent !== null; };
  const nm = e => e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + ' "' + (e.textContent || '').trim().slice(0, 24) + '"';
  const out = { contrast: [], noname: [], nolabel: [] };
  for (const e of document.querySelectorAll('body *')) {
    if (!vis(e) || e.closest('svg') || e.closest('.chart-tip')) continue;
    if ([...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) {
      const cs = getComputedStyle(e), fg = parse(cs.color), bg = bgOf(e), fs = parseFloat(cs.fontSize);
      const need = (fs >= 24 || (fs >= 18.66 && +cs.fontWeight >= 700)) ? 3 : 4.5;
      if (fg && ratio({ r: fg.r * fg.a + bg.r * (1 - fg.a), g: fg.g * fg.a + bg.g * (1 - fg.a), b: fg.b * fg.a + bg.b * (1 - fg.a) }, bg) < need - 0.01) out.contrast.push(nm(e));
    }
    if (e.matches('button') && !(e.textContent.trim() || e.getAttribute('aria-label') || e.title)) out.noname.push(nm(e));
    if (e.matches('input:not([type=hidden]):not([type=file]),select,textarea') && !(e.closest('label') || e.getAttribute('aria-label') || (e.id && document.querySelector(`label[for="${e.id}"]`)))) out.nolabel.push(nm(e));
  }
  return out;
}"""


class Checks:
    def __init__(self):
        self.n_fail = 0

    def __call__(self, ok, msg):
        print(("PASS  " if ok else "FAIL  ") + msg)
        if not ok:
            self.n_fail += 1


def port_open(port):
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8819)
    ap.add_argument("--shots", help="folder for screenshots")
    a = ap.parse_args()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright is not installed: python -m pip install playwright && python -m playwright install chromium")
        return 2
    srv = None
    if not port_open(a.port):
        srv = subprocess.Popen([sys.executable, os.path.join(ROOT, "server.py"), "--port", str(a.port), "--no-browser"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            if port_open(a.port):
                break
            time.sleep(0.1)
    url = "http://127.0.0.1:%d/web/" % a.port
    if a.shots:
        os.makedirs(a.shots, exist_ok=True)
    shot = (lambda pg, name: pg.screenshot(path=os.path.join(a.shots, name + ".png"))) if a.shots else (lambda pg, name: None)
    ok = Checks()
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={"width": 1440, "height": 900})
            errors = []
            pg.on("pageerror", lambda e: errors.append(str(e)))
            # console errors from this app; a web font that cannot be fetched (offline) is not one
            local = lambda m: "127.0.0.1" in (m.location or {}).get("url", "127.0.0.1")
            pg.on("console", lambda m: errors.append(m.text) if m.type == "error" and local(m) else None)
            pg.goto(url)
            pg.wait_for_selector("#boot", state="detached", timeout=60000)
            pg.evaluate("localStorage.clear()")
            pg.reload()
            pg.wait_for_selector("#boot", state="detached", timeout=60000)
            idle = lambda: pg.wait_for_function("document.querySelector('#busy').hidden", timeout=300000)

            # every step opens and every page passes the audit
            for s in pg.eval_on_selector_all("#steps button", "bs => bs.map(b => b.dataset.s)"):
                pg.click('#steps button[data-s="%s"]' % s)
                pg.wait_for_timeout(250)
                r = pg.evaluate(AUDIT_JS)
                ok(not r["contrast"] and not r["noname"] and not r["nolabel"],
                   "step %-8s contrast / names / labels %s" % (s, "" if not any(r.values()) else r))
            ok(pg.eval_on_selector("#steps", "s => s.scrollWidth <= s.clientWidth + 1"), "all ten steps fit in the top bar")

            # design search and route layout
            pg.click('#steps button[data-s="design"]')
            pg.click("#btnSearch")
            idle()
            pg.click('#steps button[data-s="results"]')
            pg.wait_for_timeout(500)
            ok(pg.locator(".crit").count() > 3, "results list the EN 13201 criteria")
            pg.click('#steps button[data-s="layout"]')
            pg.click("#btnRoute")
            idle()
            pg.wait_for_timeout(800)
            info = pg.evaluate("""async () => { const v = document.querySelector('#v3d').__street3d;
                v.invalidate(); await new Promise(r => setTimeout(r, 300));
                const f0 = v.frames; await new Promise(r => setTimeout(r, 1500));
                return { calls: v.renderer.info.render.calls, geoms: v.renderer.info.memory.geometries, idle: v.frames - f0 }; }""")
            ok(info["calls"] <= 60, "3D route view draws in %d calls (instanced)" % info["calls"])
            ok(info["idle"] == 0, "3D view renders only on demand (%d frames while idle)" % info["idle"])
            g0 = info["geoms"]
            g1 = pg.evaluate("() => { const v = document.querySelector('#v3d').__street3d; for (let i = 0; i < 5; i++) v.build(v.data, false); v.renderer.render(v.scene, v.camera); return v.renderer.info.memory.geometries; }")
            ok(g1 <= g0, "no geometry leak over 5 rebuilds (%d -> %d)" % (g0, g1))
            for cam in ("driver", "bird"):
                pg.click('[data-cam="%s"]' % cam)
                pg.wait_for_timeout(500)
                shot(pg, "3d_" + cam)

            # viewer tabs: arrow keys move between tabs (WAI-ARIA tabs)
            pg.focus('#vtabs button[aria-selected="true"]')
            pg.keyboard.press("ArrowRight")
            sel = pg.evaluate("document.activeElement.getAttribute('aria-selected') + ' ' + document.activeElement.dataset.v")
            ok(sel.startswith("true"), "Arrow key moves to the next viewer tab (%s)" % sel)

            # interactive charts
            pg.click("#tab-route")
            pg.wait_for_timeout(500)
            ok(pg.locator("#vroute svg.chart.d3 rect.sbar").count() > 3, "span chart drawn with D3")
            pg.focus("#vroute svg.chart.d3 rect.sbar")
            pg.wait_for_timeout(150)
            ok(pg.locator("#vroute .chart-tip:not([hidden])").count() == 1, "span values shown on keyboard focus")
            pg.keyboard.press("ArrowRight")
            ok(pg.evaluate("document.activeElement.matches('rect.sbar')"), "Arrow key moves to the next span")
            shot(pg, "chart_spans")
            pg.click("#tab-profile")
            pg.wait_for_timeout(400)
            ok(pg.locator("#vprofile g.pole").count() > 3, "profile chart shows the columns")
            pg.focus("#vprofile g.pole")
            pg.wait_for_timeout(150)
            tip = pg.inner_text("#vprofile .chart-tip")
            ok("Column 1" in tip, "column tooltip explains its position: " + tip.replace("\n", " ")[:80])
            pg.click("#vprofile .chart-tools button:nth-child(1)")
            pg.wait_for_timeout(400)
            ok(pg.locator("#vprofile .chart-tools button").count() == 3, "zoom buttons available without a mouse wheel")
            shot(pg, "chart_profile")

            # help badges by keyboard
            pg.click('#steps button[data-s="road"]')
            pg.wait_for_timeout(300)
            pg.focus(".qm")
            pg.keyboard.press("Shift+Tab")
            pg.keyboard.press("Tab")
            pg.wait_for_timeout(150)
            ok(pg.evaluate("!document.getElementById('fieldtip').hidden"), "help text appears when Tab reaches a ? badge")
            lab = pg.get_attribute(".qm", "aria-label")
            ok(lab != "Explain" and lab.startswith("Explain"), "help badge names its field: " + lab)

            # undo
            n0 = pg.locator(".strip[data-i]").count()
            pg.click('[data-rm="0"]')
            pg.click(".toast:last-child .toastact")
            pg.wait_for_timeout(200)
            ok(pg.locator(".strip[data-i]").count() == n0, "Undo restores a removed strip")

            # columns (EN 40-3-1 / 40-3-3) and the maintenance factor (CIE 154)
            pg.click('#steps button[data-s="struct"]')
            pg.wait_for_timeout(300)
            pg.click("#btnSt")
            idle()
            pg.wait_for_timeout(300)
            use = pg.inner_text("#stOut table tr:nth-child(2) td:nth-child(4)")
            ok(use.strip().endswith("%"), "column check gives a utilisation (%s)" % use.strip())

            # report dialog: focus in, Escape closes, focus back to the opener
            pg.click('#steps button[data-s="report"]')
            pg.wait_for_timeout(300)
            pg.focus("#btnRep")
            pg.keyboard.press("Enter")
            pg.wait_for_selector("#reportOverlay", timeout=60000)
            ok(pg.evaluate("document.activeElement.id") == "repPrint", "report dialog takes focus")
            pg.keyboard.press("Escape")
            pg.wait_for_timeout(200)
            ok(pg.locator("#reportOverlay").count() == 0 and pg.evaluate("document.activeElement.id") == "btnRep",
               "Escape closes the report and returns focus")

            # maintenance factor last: recalculating it clears the design
            pg.click('#steps button[data-s="lum"]')
            pg.wait_for_timeout(300)
            pg.click('[data-mm="cie154"]')
            pg.wait_for_timeout(200)
            pg.select_option("#mIp", "IP23")
            pg.click("#mCalc")
            idle()
            txt = pg.inner_text("#mOut")
            ok("LMF" in txt and "IP" in txt, "CIE 154 maintenance factor for an IP23 luminaire: " + txt.split("—")[0].strip())

            # more than four luminaires: the "search every luminaire in full" box and the quick pass
            pg.evaluate("""() => { const P = JSON.parse(localStorage.getItem('sl.project')); const b = P.luminaires.led80;
                for (let i = 1; i <= 4; i++) P.luminaires['x' + i] = Object.assign({}, b, {name: 'LED copy ' + i, lamp_flux: b.lamp_flux * (1 + 0.05 * i)});
                P.search = Object.assign(P.search || {}, {phots: Object.keys(P.luminaires), heights: [8, 10], overhangs: [0, 1], tilts: [0, 5], full: false});
                localStorage.setItem('sl.project', JSON.stringify(P)); }""")
            pg.reload()
            pg.wait_for_selector("#boot", state="detached", timeout=60000)
            pg.click('#steps button[data-s="design"]')
            ok(pg.locator("#sFull").count() == 1 and not pg.is_checked("#sFull"),
               "with more than four luminaires the 'search every luminaire in full' box is offered, unticked")
            pg.click("#btnSearch")
            idle()
            summ = pg.locator("#cands details summary").first.inner_text() if pg.locator("#cands details").count() else ""
            ok("Quick pass" in summ and "best 3" in summ, "quick pass ranks the luminaires: " + summ)

            # phone width
            m = b.new_page(viewport={"width": 390, "height": 844})
            m.goto(url)
            m.wait_for_selector("#boot", state="detached", timeout=60000)
            m.click('#steps button[data-s="road"]')
            ok(m.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), "no sideways scrolling at phone width")
            shot(m, "phone_road")
            ok(not errors, "no page or console errors %s" % (errors[:3] if errors else ""))
            b.close()
    finally:
        if srv:
            srv.terminate()
    print("\n%s" % ("All checks passed." if not ok.n_fail else "%d check(s) failed." % ok.n_fail))
    return 1 if ok.n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
