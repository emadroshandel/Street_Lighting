# Street Lighting — road lighting design to EN 13201, CIE 140 and IES RP-8.
# Copyright (C) 2026 Emad Roshandel — GPL-3.0-or-later (see LICENSE)
"""EN 13201-3:2015 photometric performance of a straight road section.

The road is described by a cross-section (a list of strips from y = 0
upward: footways, verges, carriageways, medians, cycle tracks ...) and one or
more rows of luminaires that repeat with spacing S.  The field of
calculation is x in [0, S] between two consecutive luminaires of the
reference row (EN 13201-3 clause 7.1.2).

Every quantity is the maintained value (overall maintenance factor fM applied)
except the threshold increment, which by definition uses initial values.
"""
from __future__ import annotations

import math

import numpy as np

from . import rtables
from .geometry import Luminaire, group_intensities
from .obstacles import transmission, straight_crowns

DEG = math.pi / 180.0
EYE = 1.5            # m, observer eye height and height of the Esc / Ev plane
AGE = 23.0           # years, conventional observer (8.5.1)

TRAFFIC = ("carriageway",)
PEDESTRIAN = ("footway", "cycleway", "parking", "shoulder", "pedestrian", "shared")


# ---------------------------------------------------------------------------
# cross-section helpers
# ---------------------------------------------------------------------------
def element_edges(elements):
    """Return list of (y0, y1) for the elements, stacked from y = 0."""
    y = 0.0
    out = []
    for e in elements:
        w = float(e.get("width", 0.0))
        out.append((y, y + w))
        y += w
    return out


def total_width(elements):
    return sum(float(e.get("width", 0.0)) for e in elements)


# ---------------------------------------------------------------------------
# luminaire rows
# ---------------------------------------------------------------------------
def build_rows(rows, S, x_from, x_to, phot_lookup, z0=0.0):
    """Instantiate luminaires of every row between x_from and x_to.

    A row: dict(y=pole position, side=+1|-1 (luminaire faces +y / -y),
    overhang, height, tilt, phase (fraction of S), phot (key), flux (factor),
    nu_offset (deg added to the orientation, 180 flips a C270-street-side file)).
    """
    lums = []
    for ri, r in enumerate(rows):
        ph = phot_lookup(r.get("phot"))
        side = 1 if r.get("side", 1) >= 0 else -1
        y_l = float(r["y"]) + side * float(r.get("overhang", 0.0))
        H = float(r["height"])
        phase = float(r.get("phase", 0.0)) * S
        nu = (0.0 if side > 0 else 180.0) + float(r.get("nu_offset", 0.0))
        k0 = math.floor((x_from - phase) / S) - 1
        k1 = math.ceil((x_to - phase) / S) + 1
        for k in range(k0, k1 + 1):
            x = phase + k * S
            if x_from - 1e-9 <= x <= x_to + 1e-9:
                lums.append(Luminaire(x, y_l, z0 + H, nu=nu, tilt=float(r.get("tilt", 0.0)),
                                      rot=float(r.get("rot", 0.0)), phot=ph,
                                      flux=float(r.get("flux", 1.0)),
                                      pole=(x, float(r["y"]), z0), row=ri))
    return lums


def n_long(S):
    """EN 13201-3 Formula 27/33: number of points along the field."""
    if S <= 30.0:
        return 10
    return int(math.ceil(S / 3.0 - 1e-9))


def n_trans(W):
    """Formula 34: smallest n >= 3 giving d <= 1.5 m."""
    return max(3, int(math.ceil(W / 1.5 - 1e-9)))


# ---------------------------------------------------------------------------
# point quantities
# ---------------------------------------------------------------------------
def _with_trees(I, Lp, P, crowns):
    if crowns is not None and len(crowns):
        return I * transmission(Lp, P, crowns)
    return I


def horizontal_E(lums, P, fM=1.0, I=None, crowns=None):
    """Maintained horizontal illuminance at points P (N, 3) — Formula 29."""
    if not lums:
        return np.zeros(len(P))
    Lp = np.array([l.pos for l in lums])
    if I is None:
        I = _with_trees(group_intensities(lums, P), Lp, P, crowns)
    V = Lp[:, None, :] - P[None, :, :]
    d2 = np.maximum((V ** 2).sum(-1), 1e-9)
    cos_e = np.clip(V[..., 2] / np.sqrt(d2), 0.0, 1.0)
    return fM * (I * cos_e / d2).sum(0)


def illuminance_components(lums, P, fM=1.0, directions=(0.0, 180.0), vertical=True, crowns=None):
    """Eh, Ehs at ground points; Esc and Ev at 1.5 m for each direction (deg).

    Returns dict of arrays. Direction 0 = facing +x (looking along the road
    toward +x, i.e. the vertical plane / semi-cylinder faces -x... see note):
    the flat face normal of the semi-cylinder points to `direction`, so the
    curved face receives light coming from that direction.
    """
    out = {}
    if not lums:
        z = np.zeros(len(P))
        out.update(Eh=z, Ehs=z)
        for d in directions:
            out["Esc_%d" % d] = z
            out["Ev_%d" % d] = z
        return out
    Lp = np.array([l.pos for l in lums])
    # ground
    I = _with_trees(group_intensities(lums, P), Lp, P, crowns)
    V = Lp[:, None, :] - P[None, :, :]
    d2 = np.maximum((V ** 2).sum(-1), 1e-9)
    cos_e = np.clip(V[..., 2] / np.sqrt(d2), 0.0, 1.0)
    out["Eh"] = fM * (I * cos_e / d2).sum(0)
    out["Ehs"] = fM * (I * (1.0 + cos_e) / (4.0 * d2)).sum(0)          # Formula 30
    if not vertical:
        z = np.zeros(len(P))
        for d in directions:
            out["Esc_%d" % d] = z
            out["Ev_%d" % d] = z
        return out
    # 1.5 m plane
    P2 = P + np.array([0.0, 0.0, EYE])
    I2 = _with_trees(group_intensities(lums, P2), Lp, P2, crowns)
    V2 = Lp[:, None, :] - P2[None, :, :]
    d2b = np.maximum((V2 ** 2).sum(-1), 1e-9)
    db = np.sqrt(d2b)
    below = V2[..., 2] > 0                       # luminaire above the plane
    sin_e = np.hypot(V2[..., 0], V2[..., 1]) / db
    az = np.arctan2(V2[..., 1], V2[..., 0])      # azimuth of the light source seen from P
    for d in directions:
        a = np.abs((az - d * DEG + np.pi) % (2 * np.pi) - np.pi)    # alpha_k
        cos_a = np.cos(a)
        esc = I2 * sin_e * (1.0 + cos_a) / (math.pi * d2b)          # Formula 31
        ev = np.where(cos_a > 0, I2 * sin_e * cos_a / d2b, 0.0)     # Formula 32
        out["Esc_%d" % d] = fM * np.where(below, esc, 0.0).sum(0)
        out["Ev_%d" % d] = fM * np.where(below, ev, 0.0).sum(0)
    return out


def luminance(lums, P, obs, rt, fM=1.0, H_ref=None, apply_bounds=False, crowns=None):
    """Maintained road luminance at ground points P for an observer at obs.

    Formula 22 with tan(eps) (23) and beta (24).  By default every luminaire
    inside the r-table (tan eps <= 12, i.e. within 12 H of the point) counts.
    EN 13201-3 7.1.5 sets the boundary as *at least* 5H toward the observer and
    laterally and 12H away from the observer, so the full r-table area complies;
    it is also what reproduces the CIE 140:2019 Annex B benchmark (Uo, Ul).
    apply_bounds=True restricts the sum to that minimum 5H / 12H / 5H rectangle.
    """
    if not lums:
        return np.zeros(len(P))
    Lp = np.array([l.pos for l in lums])
    I = _with_trees(group_intensities(lums, P), Lp, P, crowns)
    H = Lp[:, 2][:, None] - P[None, :, 2]
    H = np.maximum(H, 1e-6)
    dx = Lp[:, 0][:, None] - P[None, :, 0]
    dy = Lp[:, 1][:, None] - P[None, :, 1]
    horiz = np.hypot(dx, dy)
    tan_e = horiz / H
    ox = P[:, 0] - obs[0]
    oy = P[:, 1] - obs[1]
    on = np.hypot(ox, oy)
    dot = ox[None, :] * dx + oy[None, :] * dy
    with np.errstate(invalid="ignore", divide="ignore"):
        cb = np.where(horiz > 1e-9, dot / (on[None, :] * np.maximum(horiz, 1e-12)), 1.0)
    beta = np.degrees(np.arccos(np.clip(cb, -1.0, 1.0)))
    r = rt(tan_e, beta)
    contrib = I * r / H ** 2
    if apply_bounds:
        # direction from observer to point (unit) for "toward / away from" tests
        ux = np.where(on > 0, ox / np.maximum(on, 1e-12), 1.0)
        uy = np.where(on > 0, oy / np.maximum(on, 1e-12), 0.0)
        along = dx * ux[None, :] + dy * uy[None, :]
        across = -dx * uy[None, :] + dy * ux[None, :]
        Hl = Lp[:, 2][:, None]
        ok = (along >= -5 * Hl - 1e-9) & (along <= 12 * Hl + 1e-9) & (np.abs(across) <= 5 * Hl + 1e-9)
        contrib = np.where(ok, contrib, 0.0)
    return fM * contrib.sum(0)


def veiling_luminance(lums, eye, direction=(1.0, 0.0), age=AGE, max_dist=500.0, screen=True):
    """Equivalent veiling luminance (initial) — Formulae 36..38, 40.

    Line of sight: horizontal azimuth `direction`, 1 deg below the horizontal.
    Luminaires within max_dist of the observer (measured along the road) and
    within 60 deg of the line of sight are included; with `screen`, only those
    at or below the screening plane: the plane through the eye that intersects
    the road in the transverse direction and is inclined at 20 deg to the
    horizontal (EN 13201-3 8.5.1, CIE 140:2019 8.4), i.e. dz <= along * tan 20.
    For mounting heights H <= 2 m CIE 140 applies no screening plane (screen=False).
    """
    if not lums:
        return 0.0, 0
    ex, ey, ez = eye
    ux, uy = direction
    n = math.hypot(ux, uy)
    ux, uy = ux / n, uy / n
    a = -1.0 * DEG
    sight = np.array([ux * math.cos(a), uy * math.cos(a), math.sin(a)])
    Lp = np.array([l.pos for l in lums])
    v = Lp - np.array(eye)
    dist = np.linalg.norm(v, axis=1)
    along = v[:, 0] * ux + v[:, 1] * uy
    below = (v[:, 2] <= along * TAN20 + 1e-9) if screen else np.ones(len(lums), bool)
    cos_t = np.clip((v @ sight) / np.maximum(dist, 1e-9), -1, 1)
    theta = np.degrees(np.arccos(cos_t))
    sel = (along > 0) & (along <= max_dist) & below & (theta > 0.1) & (theta <= 60.0)
    if not np.any(sel):
        return 0.0, 0
    sub = [l for l, s in zip(lums, sel) if s]
    # intensity from each luminaire toward the eye (initial: no maintenance factor)
    I = group_intensities(sub, np.array([eye], float))[:, 0]
    d = dist[sel]
    th = theta[sel]
    Ek = I * cos_t[sel] / d ** 2
    k1 = 9.86 * (1.0 + (age / 66.4) ** 4)
    # CIE 140:2019 Formula (26): the age factor multiplies the 5/theta^2 term only
    lv = np.where(th > 1.5, k1 * Ek / th ** 2,
                  Ek * (10.0 / th ** 3 + 5.0 * (1.0 + (age / 62.5) ** 4) / th ** 2))
    return float(lv.sum()), int(sel.sum())


TAN20 = math.tan(math.radians(20.0))


def observer_start(H):
    """Initial observer position before the first luminaire, and whether the 20 deg screening plane applies.

    H > 2 m: 2.75 (H - 1.5) m, Formula (39), with the screening plane.
    H <= 2 m: 60 m and the 60 deg cone only (CIE 140:2019 8.4).
    """
    if H <= 2.0:
        return -60.0, False
    return -2.75 * (H - EYE), True


def threshold_increment(Lv, Li):
    """Formula 35 — fTI in % (valid 0.05 < Li <= 5 cd/m2; clamped outside)."""
    if Li <= 0:
        return float("inf")
    return 65.0 * Lv / max(Li, 0.05) ** 0.8


# ---------------------------------------------------------------------------
# the section calculation
# ---------------------------------------------------------------------------
def _grid_long(S, x0=0.0):
    N = n_long(S)
    D = S / N
    return x0 + D / 2.0 + D * np.arange(N), D, N


def evaluate(section, rows, S, phot_lookup, fM=0.8, options=None):
    """Full EN 13201-3 evaluation of every area of the cross-section.

    section: dict(elements=[...]) — each element: kind, width, lanes, cls, surface
    rows:    list of luminaire rows (see build_rows)
    Returns a dict with one entry per area and summary data for display.
    """
    opt = dict(display=True, display_step=None, both_directions=False, ti=True,
               rho=0.2, age=AGE, vertical=True, trees=True)
    opt.update(options or {})
    elements = section["elements"]
    edges = element_edges(elements)
    Wt = total_width(elements)
    Hmax = max(float(r["height"]) for r in rows) if rows else 8.0
    if opt["ti"]:
        lums = build_rows(rows, S, -max(12 * Hmax, 60.0 + 12 * Hmax) - S, S + 520.0, phot_lookup)
        near = [l for l in lums if -12 * Hmax - S <= l.x <= S + 12 * Hmax]
    else:
        lums = near = build_rows(rows, S, -12 * Hmax - S, S + 12 * Hmax, phot_lookup)
    xs, D, N = _grid_long(S)
    crowns = straight_crowns(section, -12 * Hmax - S - 10, S + 12 * Hmax + 10) if opt["trees"] else None

    areas = []
    for ei, (e, (y0, y1)) in enumerate(zip(elements, edges)):
        kind = e.get("kind", "carriageway")
        W = y1 - y0
        cls = (e.get("cls") or "").upper()
        if W <= 0 or kind in ("median", "verge", "kerb") and not cls:
            continue
        res = dict(index=ei, kind=kind, name=e.get("name") or kind.title(), y0=y0, y1=y1,
                   width=W, cls=cls)
        # ---- illuminance grid (7.2.7) ---------------------------------------
        if kind == "carriageway":
            lanes = max(1, int(e.get("lanes", 2)))
            WL = W / lanes
            ys = []
            for j in range(lanes):
                ys += [y0 + WL * j + WL / 6.0, y0 + WL * j + WL / 2.0, y0 + WL * j + 5 * WL / 6.0]
            ys = np.array(ys)
        else:
            n = n_trans(W)
            ys = y0 + W / n * (np.arange(n) + 0.5)
        XX, YY = np.meshgrid(xs, ys, indexing="ij")
        P = np.stack([XX.ravel(), YY.ravel(), np.zeros(XX.size)], axis=1)
        comp = illuminance_components(near, P, fM, vertical=opt["vertical"], crowns=crowns)
        Eh = comp["Eh"].reshape(XX.shape)
        Eavg = float(Eh.mean())
        Emin = float(Eh.min())
        res.update(E_avg=Eavg, E_min=Emin, E_max=float(Eh.max()),
                   U0_E=Emin / Eavg if Eavg > 0 else 0.0,
                   grid_x=xs.tolist(), grid_y=ys.tolist(), grid_E=Eh.T.round(4).tolist())
        Ehs = comp["Ehs"].reshape(XX.shape)
        res.update(Ehs_avg=float(Ehs.mean()),
                   U0_hs=float(Ehs.min() / Ehs.mean()) if Ehs.mean() > 0 else 0.0)
        esc = np.minimum(comp["Esc_0"], comp["Esc_180"])
        ev = np.minimum(comp["Ev_0"], comp["Ev_180"])
        res.update(Esc_min=float(esc.min()), Ev_min=float(ev.min()))

        # ---- luminance (7.1) ------------------------------------------------
        if kind == "carriageway":
            rt = rtables.get(e.get("surface", "R3"))
            lanes = max(1, int(e.get("lanes", 2)))
            WL = W / lanes
            obs_list = []
            Lgrids = []
            per_obs = []
            for j in range(lanes):
                oy = y0 + WL * (j + 0.5)
                obs = (xs[0] - D / 2.0 - 60.0, oy, EYE)
                Lp = luminance(near, P, obs, rt, fM, crowns=crowns).reshape(XX.shape)
                Lavg = float(Lp.mean())
                Lmin = float(Lp.min())
                # longitudinal uniformity on the centre line of the observer's lane
                cl = Lp[:, 3 * j + 1]
                Ul = float(cl.min() / cl.max()) if cl.max() > 0 else 0.0
                per_obs.append(dict(lane=j + 1, obs_y=oy, L_avg=Lavg,
                                    U0=Lmin / Lavg if Lavg > 0 else 0.0, Ul=Ul,
                                    L_min=Lmin, L_max=float(Lp.max())))
                obs_list.append(obs)
                Lgrids.append(Lp)
            res["observers"] = per_obs
            res["L_avg"] = min(o["L_avg"] for o in per_obs)
            res["U0_L"] = min(o["U0"] for o in per_obs)
            res["Ul"] = min(o["Ul"] for o in per_obs)
            res["grid_L"] = Lgrids[0].T.round(5).tolist()
            res["Q0"] = rt.Q0
            res["surface"] = rt.name
            # ---- threshold increment (8.5) ----------------------------------
            if opt["ti"]:
                ti_max, lv_at, n_used = 0.0, 0.0, 0
                Hr = float(rows[0]["height"]) if rows else 8.0
                # first luminaire of the field: x = 0 for the reference row
                x_start, screen = observer_start(Hr)
                for j, o in enumerate(per_obs):
                    Li = o["L_avg"] / fM if fM > 0 else o["L_avg"]
                    lane_ti, lane_lv = 0.0, 0.0
                    for i in range(N):
                        eye = (x_start + i * D, o["obs_y"], EYE)
                        Lv, nused = veiling_luminance(lums, eye, age=opt["age"], screen=screen)
                        ti = threshold_increment(Lv, Li)
                        if ti > lane_ti:
                            lane_ti, lane_lv = ti, Lv
                        if ti > ti_max:
                            ti_max, lv_at, n_used = ti, Lv, nused
                    # CIE 140:2019 Table B.3 reports TI and Lv for each observer lane
                    o["TI"] = lane_ti
                    o["Lv"] = lane_lv
                res["TI"] = ti_max
                res["Lv"] = lv_at
                res["TI_luminaires"] = n_used
            # ---- edge illuminance ratio (8.6) -------------------------------
            res["REI"] = _rei(near, elements, edges, ei, xs, fM, WL, crowns)
        elif opt["ti"] and cls.startswith(("C", "P")):
            # Annex C of EN 13201-2 / 8.5.3: Lambertian luminance rho*E/pi
            Li = opt["rho"] * (Eavg / fM if fM > 0 else Eavg) / math.pi
            ti_max = 0.0
            Hr = float(rows[0]["height"]) if rows else 6.0
            x_start, screen = observer_start(Hr)
            yc = 0.5 * (y0 + y1)
            for i in range(N):
                Lv, _ = veiling_luminance(lums, (x_start + i * D, yc, EYE), age=opt["age"], screen=screen)
                ti_max = max(ti_max, threshold_increment(Lv, Li))
            res["TI"] = ti_max
            res["TI_note"] = "Lambertian surface rho = %.2f (EN 13201-3 8.5.3)" % opt["rho"]
        areas.append(res)

    out = dict(S=S, fM=fM, N=N, D=D, areas=areas, width=Wt,
               luminaires=[l.to_dict() for l in near if -0.01 <= l.x <= S + 0.01])
    if opt["display"]:
        out["display"] = display_grids(section, rows, S, phot_lookup, fM, near, opt.get("display_step"),
                                       crowns)
    if crowns is not None and len(crowns):
        out["trees"] = [dict(x=float(c[0]), y=float(c[1]), zc=float(c[2]), r=float(c[3]), rv=float(c[4]))
                        for c in crowns if -0.5 * S - 3 <= c[0] <= 1.5 * S + 3]
    return out


def _rei(lums, elements, edges, ei, xs, fM, WL, crowns=None):
    """Edge illuminance ratio for carriageway element ei (EN 13201-3 8.6).

    An edge is not assessed (value None, with the reason in res["skipped"]) when
    * an area with its own lighting class lies within the strip width beyond it
      (EN 13201-2 Table 1 note d: REI applies only where no traffic area with its
      own lighting requirement adjoins the carriageway), or
    * it faces another carriageway at 10 m or less: both are then one carriageway
      (EN 13201-3 8.6), or
    * nothing lies beyond it.
    """
    y0, y1 = edges[ei]
    res = {"skipped": {}}
    for side, (edge, outward) in (("low", (y0, -1)), ("high", (y1, +1))):
        # unobstructed width beyond the edge (all consecutive non-carriageway strips)
        avail = 0.0
        lit_by_class = None
        k = ei + outward
        while 0 <= k < len(elements) and elements[k].get("kind") != "carriageway":
            if lit_by_class is None and avail < WL - 1e-9 and elements[k].get("cls"):
                lit_by_class = "%s (%s)" % (elements[k].get("name") or elements[k].get("kind"), elements[k]["cls"])
            avail += float(elements[k].get("width", 0.0))
            k += outward
        faces_carriageway = 0 <= k < len(elements)
        if avail <= 0.05:
            res[side] = None
            res["skipped"][side] = "no strip beyond this edge"
            continue
        if faces_carriageway and avail <= 10.0:
            res[side] = None
            res["skipped"][side] = "median of %.1f m: treated as one carriageway" % avail
            continue
        if lit_by_class:
            res[side] = None
            res["skipped"][side] = "adjoining %s has its own lighting class" % lit_by_class
            continue
        Ws = min(WL, avail)
        d = Ws / 3.0
        yin = edge - outward * (d / 2 + d * np.arange(3))
        yout = edge + outward * (d / 2 + d * np.arange(3))
        XX, YY = np.meshgrid(xs, np.concatenate([yin, yout]), indexing="ij")
        P = np.stack([XX.ravel(), YY.ravel(), np.zeros(XX.size)], 1)
        E = horizontal_E(lums, P, fM, crowns=crowns).reshape(XX.shape)
        ein, eout = float(E[:, :3].mean()), float(E[:, 3:].mean())
        res[side] = eout / ein if ein > 0 else 0.0
    vals = [v for kk, v in res.items() if kk in ("low", "high") and v is not None]
    res["value"] = min(vals) if vals else None
    return res


def display_grids(section, rows, S, phot_lookup, fM, lums=None, step=None, crowns=None):
    """Fine grids for false-colour maps and isolines over two spans."""
    elements = section["elements"]
    Wt = total_width(elements)
    span = 2 * S
    if step is None:
        step = max(0.25, min(1.0, span / 160.0))
    margin = 2.0
    xs = np.arange(-S * 0.5, S * 1.5 + 1e-9, step)
    ys = np.arange(-margin, Wt + margin + 1e-9, max(0.2, min(0.5, Wt / 60.0)))
    if lums is None:
        Hmax = max(float(r["height"]) for r in rows)
        lums = build_rows(rows, S, -12 * Hmax - S, S + 12 * Hmax, phot_lookup)
    XX, YY = np.meshgrid(xs, ys, indexing="ij")
    P = np.stack([XX.ravel(), YY.ravel(), np.zeros(XX.size)], 1)
    E = horizontal_E(lums, P, fM, crowns=crowns).reshape(XX.shape)
    out = dict(x=xs.round(3).tolist(), y=ys.round(3).tolist(), E=E.T.round(3).tolist())
    # luminance seen from the first lane of the first carriageway
    edges = element_edges(elements)
    for e, (y0, y1) in zip(elements, edges):
        if e.get("kind") == "carriageway":
            rt = rtables.get(e.get("surface", "R3"))
            lanes = max(1, int(e.get("lanes", 2)))
            obs = (-S * 0.5 - 60.0, y0 + (y1 - y0) / lanes / 2.0, EYE)
            L = luminance(lums, P, obs, rt, fM, crowns=crowns).reshape(XX.shape)
            out["L"] = L.T.round(4).tolist()
            out["L_obs"] = list(obs)
            break
    return out
