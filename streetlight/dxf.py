# Street Lighting — road lighting design to EN 13201, CIE 140 and IES RP-8.
# Copyright (C) 2026 Emad Roshandel — GPL-3.0-or-later (see LICENSE)
"""Minimal DXF R12 (AC1009) writer and the engineering drawing builders.

R12 ASCII is read by every CAD program (AutoCAD, BricsCAD, LibreCAD,
QCAD, DraftSight, FreeCAD).  Units are metres.
"""
from __future__ import annotations

import math

import numpy as np

from . import contours as C
from .calc import element_edges

LAYERS = {  # name: ACI colour
    "ROAD-EDGE": 7, "ROAD-LANE": 8, "CENTRELINE": 1, "CHAINAGE": 8, "KERB": 7,
    "POLE": 5, "LUMINAIRE": 2, "ARM": 5, "TREE": 3, "CABLE": 6, "PILLAR": 4,
    "ISOLUX": 30, "ISOLUX-TEXT": 30, "ISOLUM": 140, "TEXT": 7, "TITLE": 7, "FEATURE": 1,
}


class DXF:
    def __init__(self):
        self.ent = []

    def _w(self, *pairs):
        for c, v in pairs:
            self.ent.append("%d\n%s\n" % (c, v))

    def line(self, a, b, layer="0"):
        self._w((0, "LINE"), (8, layer), (10, "%.4f" % a[0]), (20, "%.4f" % a[1]), (30, "0.0"),
                (11, "%.4f" % b[0]), (21, "%.4f" % b[1]), (31, "0.0"))

    def polyline(self, pts, layer="0", closed=False, z=False):
        if len(pts) < 2:
            return
        self._w((0, "POLYLINE"), (8, layer), (66, 1), (10, "0.0"), (20, "0.0"), (30, "0.0"),
                (70, (1 if closed else 0) | (8 if z else 0)))
        for p in pts:
            self._w((0, "VERTEX"), (8, layer), (10, "%.4f" % p[0]), (20, "%.4f" % p[1]),
                    (30, "%.4f" % (p[2] if z and len(p) > 2 else 0.0)), (70, 32 if z else 0))
        self._w((0, "SEQEND"), (8, layer))

    def circle(self, c, r, layer="0"):
        self._w((0, "CIRCLE"), (8, layer), (10, "%.4f" % c[0]), (20, "%.4f" % c[1]), (30, "0.0"),
                (40, "%.4f" % r))

    def text(self, p, s, h=0.5, layer="TEXT", rot=0.0, align=0):
        s = str(s).replace("\n", " ")
        self._w((0, "TEXT"), (8, layer), (10, "%.4f" % p[0]), (20, "%.4f" % p[1]), (30, "0.0"),
                (40, "%.3f" % h), (1, s), (50, "%.2f" % rot))
        if align:
            self._w((72, align), (11, "%.4f" % p[0]), (21, "%.4f" % p[1]), (31, "0.0"))

    def tostring(self):
        out = ["0\nSECTION\n2\nHEADER\n9\n$ACADVER\n1\nAC1009\n9\n$INSUNITS\n70\n6\n0\nENDSEC\n",
               "0\nSECTION\n2\nTABLES\n0\nTABLE\n2\nLAYER\n70\n%d\n" % len(LAYERS)]
        for name, col in LAYERS.items():
            out.append("0\nLAYER\n2\n%s\n70\n0\n62\n%d\n6\nCONTINUOUS\n" % (name, col))
        out.append("0\nENDTAB\n0\nENDSEC\n0\nSECTION\n2\nENTITIES\n")
        out += self.ent
        out.append("0\nENDSEC\n0\nEOF\n")
        return "".join(out)


def _title(d, x, y, title, lines):
    w, h = 120.0, 6.0 + 2.2 * len(lines)
    d.polyline([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], "TITLE", closed=True)
    d.text((x + 2, y + h - 3.5), title, 2.0, "TITLE")
    for i, t in enumerate(lines):
        d.text((x + 2, y + h - 6.5 - 2.2 * i), t, 1.2, "TITLE")


def route_drawing(route, poles, result=None, electrical=None, title="Street lighting layout",
                  info=None, contour_quantity="E"):
    """Plan of the whole route: edges, lanes, centreline, chainage, poles,
    arms, trees, cables, pillars and isolux / isoluminance contours."""
    d = DXF()
    el = route.section["elements"]
    edges = element_edges(el)
    L = route.length
    s = np.linspace(0, L, max(2, int(L / 1.0) + 1))
    ylines = sorted({0.0} | {e[1] for e in edges})
    for y in ylines:
        P, _ = route.world(s, np.full_like(s, y))
        d.polyline(P[:, :2].tolist(), "ROAD-EDGE")
    for e, (y0, y1) in zip(el, edges):
        if e.get("kind") == "carriageway":
            n = max(1, int(e.get("lanes", 2)))
            for j in range(1, n):
                yl = y0 + (y1 - y0) * j / n
                # dashed lane line as short segments
                for a in np.arange(0, L, 12.0):
                    ss = np.array([a, min(a + 6.0, L)])
                    P, _ = route.world(ss, np.full_like(ss, yl))
                    d.line(P[0, :2], P[1, :2], "ROAD-LANE")
    P, _ = route.world(s, np.full_like(s, route.ref_y))
    d.polyline(P[:, :2].tolist(), "CENTRELINE")
    for ch in np.arange(0, L + 1e-6, 20.0):
        p, h = route.world(ch, route.ref_y)
        q, _ = route.world(ch, -2.5)
        d.line(p[:2], q[:2], "CHAINAGE")
        d.text(q[:2], "%.0f" % ch, 0.8, "CHAINAGE", rot=math.degrees(float(h)) - 90)
    for p in poles:
        side = 1 if p["side"] >= 0 else -1
        base, h = route.world(p["s"], p["y"])
        head, _ = route.world(p["s"], p["y"] + side * p["overhang"])
        d.circle(base[:2], 0.15, "POLE")
        if p["overhang"] > 0:
            d.line(base[:2], head[:2], "ARM")
        d.circle(head[:2], 0.3, "LUMINAIRE")
        lab, _ = route.world(p["s"], p["y"] - side * 1.2)
        d.text(lab[:2], "%s H%.0f" % (p["id"], p["H"]), 0.6, "TEXT", rot=math.degrees(float(h)))
    for t in route.trees():
        d.circle((t["x"], t["yw"]), t["r"], "TREE")
        d.circle((t["x"], t["yw"]), 0.2, "TREE")
    if electrical:
        for f in electrical.get("feeders", []):
            pts = [(electrical_p["x"], electrical_p["yw"]) for electrical_p in
                   [next(pp for pp in electrical["pillars"] if pp["id"] == f["pillar"])]]
            pts += [(q["x"], q["yw"]) for q in f["poles"]]
            d.polyline(pts, "CABLE")
            mid = f["poles"][len(f["poles"]) // 2]
            d.text((mid["x"], mid["yw"] - 1.5), "%s %s mm²" % (f["id"], f["size"]), 0.6, "CABLE")
        for pp in electrical.get("pillars", []):
            x, y = pp["x"], pp["yw"]
            d.polyline([(x - 0.6, y - 0.4), (x + 0.6, y - 0.4), (x + 0.6, y + 0.4), (x - 0.6, y + 0.4)],
                       "PILLAR", closed=True)
            d.text((x + 0.8, y + 0.6), pp["id"], 0.8, "PILLAR")
    for c in route.features.get("crossings", []):
        y0, y1 = 0.0, route.W
        for yy in np.arange(y0, y1, 1.0):
            a, _ = route.world(float(c["s"]) - 1.5, yy)
            b, _ = route.world(float(c["s"]) + 1.5, yy)
            d.line(a[:2], b[:2], "FEATURE")
    if result and result.get("display"):
        for m in result["display"]["meshes"]:
            Z = np.array(m[contour_quantity] if m.get(contour_quantity) else m["E"], float).reshape(m["ns"], m["ny"])
            if Z.max() <= 0:
                continue
            levels = C.nice_levels(float(Z.min()), float(Z.max()), 6)
            for cs in C.contour_set(m["y"], m["s"], Z, levels):
                for ln in cs["lines"]:
                    arr = np.array(ln)
                    P, _ = route.world(arr[:, 1], arr[:, 0])
                    d.polyline(P[:, :2].tolist(), "ISOLUX")
                    if len(ln) > 6:
                        k = len(ln) // 2
                        d.text(P[k, :2], ("%g" % cs["level"]), 0.5, "ISOLUX-TEXT")
    xs = []
    P, _ = route.world(s, np.full_like(s, 0.0))
    xmin, ymin = P[:, 0].min(), P[:, 1].min()
    _title(d, xmin, ymin - 30, title, info or [])
    return d.tostring()


def section_drawing(section, design, result, title="Typical section and isolux plan", info=None):
    """Straight-section drawing: two spans in plan with isolux lines and a
    cross-section with the column elevation."""
    d = DXF()
    el = section["elements"]
    edges = element_edges(el)
    S = design["S"]
    x0, x1 = -0.5 * S, 1.5 * S
    for y in sorted({0.0} | {e[1] for e in edges}):
        d.line((x0, y), (x1, y), "ROAD-EDGE")
    for e, (y0, y1) in zip(el, edges):
        d.text((x0 - 1.0, 0.5 * (y0 + y1)), "%s %.2f m" % (e.get("name") or e.get("kind"), y1 - y0), 0.5,
               "TEXT", align=2)
        if e.get("kind") == "carriageway":
            n = max(1, int(e.get("lanes", 2)))
            for j in range(1, n):
                yl = y0 + (y1 - y0) * j / n
                for a in np.arange(x0, x1, 6.0):
                    d.line((a, yl), (min(a + 3.0, x1), yl), "ROAD-LANE")
    for l in result.get("luminaires", []):
        pass
    for r in design["rows"]:
        side = 1 if r["side"] >= 0 else -1
        ph = r.get("phase", 0.0) * S
        for k in range(-1, 3):
            x = ph + k * S
            if x0 - 1e-6 <= x <= x1 + 1e-6:
                d.circle((x, r["y"]), 0.15, "POLE")
                yl = r["y"] + side * r["overhang"]
                if r["overhang"] > 0:
                    d.line((x, r["y"]), (x, yl), "ARM")
                d.circle((x, yl), 0.3, "LUMINAIRE")
    disp = result.get("display")
    if disp:
        Z = np.array(disp["E"], float)
        levels = C.nice_levels(float(Z.min()), float(Z.max()), 8)
        for cs in C.contour_set(disp["x"], disp["y"], Z, levels):
            for ln in cs["lines"]:
                d.polyline(ln, "ISOLUX")
                if len(ln) > 8:
                    d.text(ln[len(ln) // 2], "%g lx" % cs["level"], 0.35, "ISOLUX-TEXT")
    # dimension text
    d.text((0.5 * S, -2.0), "S = %.2f m" % S, 0.6, "TEXT", align=1)
    # cross-section below the plan
    W = sum(float(e["width"]) for e in el)
    yb = -25.0
    for e, (y0, y1) in zip(el, edges):
        z = 0.15 if e.get("kind") in ("footway", "verge", "median", "cycleway") else 0.0
        d.polyline([(y0, yb + z), (y1, yb + z)], "ROAD-EDGE")
        d.text((0.5 * (y0 + y1), yb - 1.0), e.get("name") or e.get("kind"), 0.4, "TEXT", align=1)
    for r in design["rows"]:
        side = 1 if r["side"] >= 0 else -1
        H = r["height"]
        d.line((r["y"], yb), (r["y"], yb + H), "POLE")
        yl = r["y"] + side * r["overhang"]
        d.line((r["y"], yb + H), (yl, yb + H), "ARM")
        d.circle((yl, yb + H), 0.25, "LUMINAIRE")
        d.text((r["y"] - side * 0.4, yb + H / 2), "H = %.1f m" % H, 0.45, "TEXT", rot=90)
    _title(d, x0, yb - 25, title, info or [])
    return d.tostring()
