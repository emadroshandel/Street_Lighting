# Street Lighting — road lighting design to EN 13201, CIE 140 and IES RP-8.
# Copyright (C) 2026 Emad Roshandel — GPL-3.0-or-later (see LICENSE)
"""Road model along a route: horizontal alignment, vertical profile,
cross-section, trees and other features, and the pole layout.

Coordinates
-----------
* chainage s (m) along the reference line (the alignment)
* offset t (m), positive to the left of the direction of increasing s
* the cross-section strips are stacked from y = 0 (right-most edge when
  looking along +s ... see below) and the alignment runs at y = ref_y;
  t = y - ref_y, so y = 0 is the right-hand edge seen from the start.

The horizontal alignment is built from straights and circular arcs (from a
parametric list, or from a polyline with fillet radii) and sampled densely.
"""
from __future__ import annotations

import math

import numpy as np

from .calc import total_width

DEG = math.pi / 180.0


# ---------------------------------------------------------------------------
# horizontal alignment
# ---------------------------------------------------------------------------
class Alignment:
    def __init__(self, s, x, y, heading, kappa):
        self.s = np.asarray(s, float)
        self.x = np.asarray(x, float)
        self.y = np.asarray(y, float)
        self.h = np.unwrap(np.asarray(heading, float))
        self.k = np.asarray(kappa, float)

    @property
    def length(self):
        return float(self.s[-1])

    def at(self, s):
        """Position, heading and curvature; extrapolated along the end
        tangents beyond the ends (used for observers before the start)."""
        s = np.asarray(s, float)
        sc = np.clip(s, 0.0, self.length)
        x = np.interp(sc, self.s, self.x)
        y = np.interp(sc, self.s, self.y)
        h = np.interp(sc, self.s, self.h)
        k = np.interp(sc, self.s, self.k)
        ext = s - sc
        if np.any(ext != 0):
            x = x + ext * np.cos(h)
            y = y + ext * np.sin(h)
            k = np.where(ext != 0, 0.0, k)
        return x, y, h, k

    def point(self, s, t=0.0):
        """World (x, y) of chainage s and left offset t; also heading."""
        x, y, h, _ = self.at(s)
        return x - np.sin(h) * t, y + np.cos(h) * t, h

    def to_dict(self, step=2.0):
        n = max(2, int(self.length / step) + 1)
        s = np.linspace(0, self.length, n)
        x, y, h, k = self.at(s)
        return dict(s=s.round(3).tolist(), x=x.round(3).tolist(), y=y.round(3).tolist(),
                    h=h.round(5).tolist(), k=k.round(6).tolist(), length=self.length)


def from_segments(segments, x0=0.0, y0=0.0, h0=0.0, step=0.5):
    """segments: [{type:'straight', length}, {type:'arc', radius, length|angle, turn:'L'|'R'}]"""
    """h0 in radians."""
    S, X, Y, H, K = [0.0], [x0], [y0], [float(h0)], [0.0]
    x, y, h, s = x0, y0, H[0], 0.0
    for seg in segments:
        typ = seg.get("type", "straight")
        if typ == "straight":
            L = float(seg.get("length", 0))
            k = 0.0
        else:
            R = float(seg.get("radius") or 0)
            if R <= 0:
                raise ValueError("Every bend needs a radius greater than zero.")
            L = float(seg["length"]) if seg.get("length") else abs(float(seg.get("angle", 0))) * DEG * R
            k = (1.0 if str(seg.get("turn", "L")).upper().startswith("L") else -1.0) / R
        n = max(1, int(math.ceil(L / step)))
        ds = L / n
        for _ in range(n):
            if k == 0:
                x += ds * math.cos(h)
                y += ds * math.sin(h)
            else:
                hn = h + k * ds
                x += (math.sin(hn) - math.sin(h)) / k
                y += -(math.cos(hn) - math.cos(h)) / k
                h = hn
            s += ds
            S.append(s); X.append(x); Y.append(y); H.append(h); K.append(k)
    return Alignment(S, X, Y, H, K)


def from_polyline(points, radius=None, radii=None, step=0.5):
    """Straights between vertices, joined by tangent arcs of the given radius."""
    P = [tuple(map(float, p[:2])) for p in points]
    # drop duplicate consecutive points
    Q = [P[0]]
    for p in P[1:]:
        if math.hypot(p[0] - Q[-1][0], p[1] - Q[-1][1]) > 1e-6:
            Q.append(p)
    P = Q
    if len(P) < 2:
        raise ValueError("A route needs at least two distinct points.")
    if len(P) == 2 or (not radius and not radii):
        segs = []
        h0 = math.atan2(P[1][1] - P[0][1], P[1][0] - P[0][0])
        # polyline with sharp vertices: emulate with tiny arcs
        x, y, h = P[0][0], P[0][1], h0
        for i in range(len(P) - 1):
            hn = math.atan2(P[i + 1][1] - P[i][1], P[i + 1][0] - P[i][0])
            dh = (hn - h + math.pi) % (2 * math.pi) - math.pi
            if i > 0 and abs(dh) > 1e-6:
                segs.append(dict(type="arc", radius=1.0, angle=abs(dh) / DEG, turn="L" if dh > 0 else "R"))
            segs.append(dict(type="straight", length=math.hypot(P[i + 1][0] - P[i][0], P[i + 1][1] - P[i][1])))
            h = hn
        return from_segments(segs, P[0][0], P[0][1], h0, step)
    radii = radii or [radius] * len(P)
    segs = []
    h0 = math.atan2(P[1][1] - P[0][1], P[1][0] - P[0][0])
    prev_cut = 0.0
    for i in range(1, len(P) - 1):
        a, b, c = np.array(P[i - 1]), np.array(P[i]), np.array(P[i + 1])
        u1 = (b - a) / np.linalg.norm(b - a)
        u2 = (c - b) / np.linalg.norm(c - b)
        h1, h2 = math.atan2(u1[1], u1[0]), math.atan2(u2[1], u2[0])
        dh = (h2 - h1 + math.pi) % (2 * math.pi) - math.pi
        R = float(radii[i] or radius or 0.0)
        Ltan = R * math.tan(abs(dh) / 2) if R > 0 else 0.0
        len1 = np.linalg.norm(b - a) - prev_cut
        len2 = np.linalg.norm(c - b)
        lim = 0.49 * min(np.linalg.norm(b - a), len2)
        if Ltan > lim:
            Ltan = lim
            R = Ltan / math.tan(abs(dh) / 2) if abs(dh) > 1e-9 else 0.0
        segs.append(dict(type="straight", length=max(len1 - Ltan, 0.0)))
        if abs(dh) > 1e-9 and R > 0:
            segs.append(dict(type="arc", radius=R, angle=abs(dh) / DEG, turn="L" if dh > 0 else "R"))
        prev_cut = Ltan
    segs.append(dict(type="straight",
                     length=max(float(np.linalg.norm(np.array(P[-1]) - np.array(P[-2]))) - prev_cut, 0.0)))
    return from_segments(segs, P[0][0], P[0][1], h0, step)


# ---------------------------------------------------------------------------
# vertical profile
# ---------------------------------------------------------------------------
MIN_MOUNTING_HEIGHT = 2.0   # m — lowest column height the layout will place


class Profile:
    """Elevation along the chainage from PVIs with symmetric parabolic curves.

    pvis: [(s, z, L_vc)] — L_vc is the length of the vertical curve at the PVI.
    """

    def __init__(self, pvis=None, crossfall=0.0):
        rows = []
        for p in (pvis or []):
            q = [float(v) for v in (list(p) + [0.0, 0.0])[:3]]
            rows.append(tuple(q))
        self.pvis = sorted(rows)
        self.crossfall = float(crossfall)            # % (positive: falls toward +t)

    def z(self, s):
        s = np.asarray(s, float)
        if len(self.pvis) < 2:
            return np.full_like(s, self.pvis[0][1] if self.pvis else 0.0)
        S = np.array([p[0] for p in self.pvis])
        Z = np.array([p[1] for p in self.pvis])
        z = np.interp(s, S, Z)
        for i in range(1, len(self.pvis) - 1):
            si, zi, L = self.pvis[i]
            if L <= 0:
                continue
            g1 = (Z[i] - Z[i - 1]) / max(S[i] - S[i - 1], 1e-9)
            g2 = (Z[i + 1] - Z[i]) / max(S[i + 1] - S[i], 1e-9)
            a = si - L / 2
            m = (s >= a) & (s <= si + L / 2)
            x = s - a
            zc = (zi - g1 * L / 2) + g1 * x + (g2 - g1) / (2 * L) * x ** 2
            z = np.where(m, zc, z)
        return z

    def grade(self, s, ds=0.5):
        s = np.asarray(s, float)
        return (self.z(s + ds) - self.z(s - ds)) / (2 * ds)

    def curves(self):
        """List of vertical curves with type (crest / sag) and K value."""
        out = []
        S = [p[0] for p in self.pvis]
        Z = [p[1] for p in self.pvis]
        for i in range(1, len(self.pvis) - 1):
            g1 = (Z[i] - Z[i - 1]) / max(S[i] - S[i - 1], 1e-9)
            g2 = (Z[i + 1] - Z[i]) / max(S[i + 1] - S[i], 1e-9)
            A = (g2 - g1) * 100.0
            L = self.pvis[i][2]
            out.append(dict(s=S[i], z=Z[i], g1=g1 * 100, g2=g2 * 100, A=A, L=L,
                            type="crest" if A < 0 else "sag",
                            K=(L / abs(A)) if abs(A) > 1e-9 else None))
        return out


# ---------------------------------------------------------------------------
# route = alignment + profile + section + features
# ---------------------------------------------------------------------------
class Route:
    def __init__(self, alignment, profile, section, ref_y=None, features=None):
        self.al = alignment
        self.pr = profile
        self.section = section
        self.W = total_width(section["elements"])
        self.ref_y = self.W / 2.0 if ref_y is None else float(ref_y)
        self.features = features or {}

    @property
    def length(self):
        return self.al.length

    def world(self, s, y, dz=0.0):
        """World coordinates of chainage s and section coordinate y."""
        s = np.asarray(s, float)
        t = np.asarray(y, float) - self.ref_y
        x, yy, h = self.al.point(s, t)
        z = self.pr.z(s) - self.pr.crossfall / 100.0 * t + dz
        return np.stack(np.broadcast_arrays(x, yy, z), axis=-1), h

    def normal(self, s, y):
        """Unit surface normal at (s, y) including grade and cross-fall."""
        s = np.asarray(s, float)
        _, _, h, _ = self.al.at(s)
        g = self.pr.grade(s)
        cf = -self.pr.crossfall / 100.0
        tx, ty = np.cos(h), np.sin(h)
        nx, ny = -np.sin(h), np.cos(h)
        # tangent along s: (tx, ty, g); along t (left): (nx, ny, cf)
        a = np.stack([tx, ty, g], -1)
        b = np.stack([nx, ny, np.full_like(g, cf)], -1)
        n = np.cross(a, b)
        n /= np.linalg.norm(n, axis=-1, keepdims=True)
        return np.broadcast_to(n, np.broadcast(s, np.asarray(y)).shape + (3,))

    def trees(self):
        """Expand tree lines to individual crowns in world coordinates."""
        out = []
        for tl in self.features.get("tree_lines", []):
            s0 = float(tl.get("s0", 0.0))
            s1 = float(tl.get("s1", self.length))
            sp = max(float(tl.get("spacing", 8.0)), 1.0)
            y = float(tl["y"])
            base = float(tl.get("crown_base", 3.0))
            top = float(tl.get("height", 8.0))
            r = float(tl.get("crown_radius", 2.5))
            kappa = float(tl.get("density", 0.6))
            s = s0
            while s <= s1 + 1e-9:
                p, _ = self.world(s, y)
                out.append(dict(s=s, y=y, x=float(p[0]), yw=float(p[1]), z0=float(p[2]),
                                base=base, top=top, r=r, kappa=kappa,
                                species=tl.get("species", "deciduous")))
                s += sp
        for t in self.features.get("trees", []):
            p, _ = self.world(float(t["s"]), float(t["y"]))
            out.append(dict(s=float(t["s"]), y=float(t["y"]), x=float(p[0]), yw=float(p[1]),
                            z0=float(p[2]), base=float(t.get("crown_base", 3.0)),
                            top=float(t.get("height", 8.0)), r=float(t.get("crown_radius", 2.5)),
                            kappa=float(t.get("density", 0.6)), species=t.get("species", "deciduous")))
        return out

    def describe_topology(self):
        """Human-readable findings that drive the layout decisions."""
        notes = []
        al = self.al
        k = np.abs(al.k)
        s = al.s
        # horizontal curves
        in_curve = k > 1e-5
        i = 0
        while i < len(s):
            if in_curve[i]:
                j = i
                while j < len(s) and in_curve[j]:
                    j += 1
                R = 1.0 / float(np.median(k[i:j]))
                turn = "left" if np.median(al.k[i:j]) > 0 else "right"
                notes.append(dict(kind="curve", s0=float(s[i]), s1=float(s[min(j, len(s) - 1)]),
                                  R=R, turn=turn,
                                  text="Bend to the %s, R = %.0f m (ch %.0f–%.0f)" % (turn, R, s[i], s[min(j, len(s) - 1)])))
                i = j
            else:
                i += 1
        for vc in self.pr.curves():
            notes.append(dict(kind=vc["type"], s=vc["s"], A=vc["A"], K=vc["K"],
                              text="%s at ch %.0f: grades %.1f %% → %.1f %%" %
                                   ("Crest" if vc["type"] == "crest" else "Sag", vc["s"], vc["g1"], vc["g2"])))
        g = np.abs(self.pr.grade(s)) * 100
        if g.max() > 6:
            notes.append(dict(kind="grade", text="Steep grade up to %.1f %%" % g.max()))
        for tl in self.features.get("tree_lines", []):
            notes.append(dict(kind="trees", text="Tree line at y = %.1f m, crown base %.1f m, top %.1f m (ch %.0f–%.0f)" %
                              (tl["y"], tl.get("crown_base", 3), tl.get("height", 8), tl.get("s0", 0),
                               tl.get("s1", self.length))))
        for c in self.features.get("crossings", []):
            notes.append(dict(kind="crossing", s=c["s"], text="Pedestrian crossing at ch %.0f" % c["s"]))
        for j in self.features.get("junctions", []):
            notes.append(dict(kind="junction", s=j["s"], text="Junction (%s) at ch %.0f" % (j.get("side", "both"), j["s"])))
        for z in self.features.get("no_pole", []):
            notes.append(dict(kind="no_pole", text="No poles between ch %.0f and %.0f (%s)" %
                              (z["s0"], z["s1"], z.get("reason", "access"))))
        for ol in self.features.get("overhead_lines", []):
            notes.append(dict(kind="overhead", text="Overhead line %.1f m high (ch %.0f–%.0f)" %
                              (ol.get("height", 8), ol.get("s0", 0), ol.get("s1", self.length))))
        return notes


# ---------------------------------------------------------------------------
# pole layout along the route
# ---------------------------------------------------------------------------
def curve_factor(R, R_straight=1000.0, R_tight=50.0, f_tight=0.55):
    """Spacing reduction on a bend (engineering rule, verified by calculation)."""
    if R >= R_straight:
        return 1.0
    if R <= R_tight:
        return f_tight
    a = (math.log(R) - math.log(R_tight)) / (math.log(R_straight) - math.log(R_tight))
    return f_tight + (1 - f_tight) * a


def layout(route, design, options=None):
    """Place the luminaire rows of a design along the route.

    design: dict(S, rows=[...]) from the optimizer (straight-road values).
    options: curve_rule (bool), outside_on_bends (bool), crest_factor,
             start_offset (fraction of S), extra_crossing (bool)
    Returns list of poles: dict(s, y, row, side, H, overhang, tilt, flux, phot,
    reason) — reason tells why a pole is where it is.
    """
    opt = dict(curve_rule=True, outside_on_bends=True, crest_factor=0.85, start_offset=0.0,
               extra_crossing=True, tree_clearance=1.0, junction_poles=True, margin=1.0, local=[])
    opt.update(options or {})
    S = float(design["S"])
    rows = design["rows"]
    L = route.length
    al = route.al
    feats = route.features
    crests = [c for c in route.pr.curves() if c["type"] == "crest"]
    no_pole = [(float(z["s0"]), float(z["s1"])) for z in feats.get("no_pole", [])]
    tree_s = {}
    for t in route.trees():
        tree_s.setdefault(round(t["y"], 2), []).append(t["s"])

    def local_factor(s, why=None):
        f = 1.0
        if opt["curve_rule"]:
            _, _, _, k = al.at(s)
            if abs(float(k)) > 1e-6:
                fc = curve_factor(1.0 / abs(float(k)))
                if fc < 0.999 and why is not None:
                    why.append("bend R %.0f m × %.2f" % (1.0 / abs(float(k)), fc))
                f = min(f, fc)
        for c in crests:
            half = max(c["L"] / 2.0, 30.0)
            if c["s"] - half <= s <= c["s"] + half:
                if opt["crest_factor"] < f and why is not None:
                    why.append("crest × %.2f" % opt["crest_factor"])
                f = min(f, opt["crest_factor"])
        n_ref = 0
        for z in opt.get("local", []):
            if z["s0"] - 1e-6 <= s <= z["s1"] + 1e-6:
                f *= z["factor"]
                n_ref += 1
        if n_ref and why is not None:
            why.append("tightened %d× after the span check" % n_ref)
        return f * opt.get("margin", 1.0)

    def blocked(s, y):
        for a, b in no_pole:
            if a - 1e-6 <= s <= b + 1e-6:
                return True
        for ty, ss in tree_s.items():
            if abs(ty - y) < 1.5:
                for st in ss:
                    if abs(st - s) < opt["tree_clearance"]:
                        return True
        return False

    poles = []
    single = len({round(r["y"], 2) for r in rows}) == 1 and len(rows) == 1
    for ri, r in enumerate(rows):
        s = (float(r.get("phase", 0.0)) + opt["start_offset"]) * S
        while s <= L + 1e-6:
            reason = []
            why_f = []
            f = local_factor(s, why_f)
            # avoid blocked positions: move back (toward the previous pole) first
            if blocked(s, r["y"]):
                moved = False
                for d in np.arange(0.5, 0.3 * S, 0.5):
                    for cand in (s - d, s + d):
                        if 0 <= cand <= L and not blocked(cand, r["y"]):
                            s = cand
                            moved = True
                            reason.append("moved %.1f m to clear an obstruction" % d)
                            break
                    if moved:
                        break
            y, side = r["y"], r["side"]
            if single and opt["outside_on_bends"]:
                _, _, _, k = al.at(s)
                k = float(k)
                if abs(k) > 1.0 / 300.0:
                    # outside of the bend: left turn (k > 0) -> right side (low y)
                    lines = design.get("lines") or {}
                    if k > 0 and "left" in lines and side < 0:
                        y, side = lines["left"]["y"], +1
                        reason.append("outside of a left-hand bend")
                    elif k < 0 and "right" in lines and side > 0:
                        y, side = lines["right"]["y"], -1
                        reason.append("outside of a right-hand bend")
            if why_f:
                reason.append("next spacing × %.2f: %s" % (f / opt.get("margin", 1.0), ", ".join(why_f)))
            poles.append(dict(s=float(s), y=float(y), row=ri, side=side, H=r["height"],
                              overhang=r["overhang"], tilt=r["tilt"], flux=r.get("flux", 1.0),
                              phot=r["phot"], nu_offset=r.get("nu_offset", 0.0),
                              reason="; ".join(reason) or "regular spacing"))
            s += S * f
    # junctions: make sure a pole stands at each junction mouth
    if opt["junction_poles"]:
        for j in feats.get("junctions", []):
            sj = float(j["s"])
            for ri, r in enumerate(rows):
                near = [p for p in poles if p["row"] == ri and abs(p["s"] - sj) < 0.35 * S]
                if near:
                    p = min(near, key=lambda p: abs(p["s"] - sj))
                    p["s"] = sj
                    p["reason"] = "placed at the junction (conflict area)"
                else:
                    poles.append(dict(s=sj, y=r["y"], row=ri, side=r["side"], H=r["height"],
                                      overhang=r["overhang"], tilt=r["tilt"], flux=r.get("flux", 1.0),
                                      phot=r["phot"], nu_offset=r.get("nu_offset", 0.0),
                                      reason="added at the junction"))
    # pedestrian crossings: one luminaire before the crossing in each traffic direction (EN 13201-2 Annex B)
    if opt["extra_crossing"]:
        lines = design.get("lines") or {}
        for c in feats.get("crossings", []):
            sc = float(c["s"])
            r0 = rows[0]
            for side_key, ds in (("left", -1.0), ("right", +1.0)):
                ln = lines.get(side_key)
                if not ln:
                    continue
                target = sc + ds * float(c.get("offset", 1.0))
                # a regular column already standing on this side close to the crossing takes the
                # crossing luminaire's place instead of a second column a few metres away
                near = [p for p in poles if not p.get("crossing") and abs(p["y"] - ln["y"]) < 0.05
                        and abs(p["s"] - target) <= 0.25 * S and "junction" not in p["reason"]]
                if near:
                    p = min(near, key=lambda p: abs(p["s"] - target))
                    p.update(s=target, crossing=True,
                             reason="moved %.1f m to light the crossing (EN 13201-2 Annex B)"
                                    % abs(p["s"] - target))
                    continue
                poles.append(dict(s=sc + ds * float(c.get("offset", 1.0)), y=ln["y"], row=-1,
                                  side=ln["face"] or 1, H=min(r0["height"], 8.0), overhang=0.5,
                                  tilt=0.0, flux=r0.get("flux", 1.0), phot=c.get("phot", r0["phot"]),
                                  nu_offset=r0.get("nu_offset", 0.0), crossing=True,
                                  reason="crossing luminaire (EN 13201-2 Annex B)"))
    poles.sort(key=lambda p: (p["s"], p["y"]))
    for i, p in enumerate(poles):
        p["id"] = "P%03d" % (i + 1)
        xy, h = route.world(p["s"], p["y"])
        p["x"], p["yw"], p["z0"] = float(xy[0]), float(xy[1]), float(xy[2])
        p["heading"] = float(h)
    # overhead line clearances
    for ol in feats.get("overhead_lines", []):
        for p in poles:
            if float(ol.get("s0", 0)) <= p["s"] <= float(ol.get("s1", L)) and \
                    abs(p["y"] - float(ol.get("y", p["y"]))) < float(ol.get("corridor", 3.0)):
                lim = float(ol.get("height", 8.0)) - float(ol.get("clearance", 1.5))
                if lim < MIN_MOUNTING_HEIGHT:
                    p["H"] = min(p["H"], MIN_MOUNTING_HEIGHT)
                    p["conflict"] = ("an overhead line leaves less than %.0f m mounting height here "
                                     "(line %.1f m, clearance %.1f m): move the line, the column or "
                                     "use another lighting method" % (MIN_MOUNTING_HEIGHT,
                                     float(ol.get("height", 8.0)), float(ol.get("clearance", 1.5))))
                    p["reason"] += "; " + p["conflict"]
                elif p["H"] > lim:
                    p["H"] = lim
                    p["reason"] += "; height limited to %.1f m by an overhead line" % lim
    # a column that could not be moved out of a no-pole zone is reported, never hidden
    for p in poles:
        for a, b in no_pole:
            if a - 1e-6 <= p["s"] <= b + 1e-6:
                msg = "stands inside the no-pole zone ch %.0f–%.0f and could not be moved clear" % (a, b)
                p["conflict"] = (p["conflict"] + "; " + msg) if p.get("conflict") else msg
                p["reason"] += "; " + msg
                break
    return poles
