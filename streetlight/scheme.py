# Street Lighting — road lighting design to EN 13201, CIE 140 and IES RP-8.
# Copyright (C) 2026 Emad Roshandel — GPL-3.0-or-later (see LICENSE)
"""Point-by-point calculation of a whole route.

The standard calculation (calc.py) assumes a straight, flat road with
regular spacing.  This module evaluates the real installation produced by
road.layout(): bends, grades, crests and sags, cross-fall, irregular
spacing, junction and crossing luminaires, and tree crowns.

* Illuminance uses the true surface normal (grade and cross-fall).
* Luminance uses a moving observer 60 m back along the alignment in the
  lane of the point, eye 1.5 m above the surface, with tan(eps) and beta
  measured in the local road plane.
* The threshold increment is evaluated from each lane at every pole of the
  reference row, the line of sight following the road (1 deg below the
  local road direction) and the 20 deg screening plane.
* Results are summarised span by span so that a failing bend, crest or
  shaded stretch can be pointed out.
"""
from __future__ import annotations

import math

import numpy as np

from . import classes, rtables
from .calc import EYE, element_edges, n_trans, observer_start, threshold_increment
from .geometry import Luminaire, group_intensities
from .obstacles import crowns_array, transmission

DEG = math.pi / 180.0


def make_luminaires(route, poles, phot_lookup):
    lums = []
    for p in poles:
        ph = phot_lookup(p["phot"])
        side = 1 if p["side"] >= 0 else -1
        y_l = p["y"] + side * p["overhang"]
        base, h = route.world(p["s"], p["y"])
        head, _ = route.world(p["s"], y_l)
        z = float(base[2]) + float(p["H"])
        nu = math.degrees(float(h)) + (0.0 if side > 0 else 180.0) + float(p.get("nu_offset", 0.0))
        l = Luminaire(head[0], head[1], z, nu=nu, tilt=p["tilt"], phot=ph, flux=p.get("flux", 1.0),
                      pole=(float(base[0]), float(base[1]), float(base[2])), row=p["row"], tag=p["id"])
        lums.append(l)
    return lums


def _area_grid(route, e, y0, y1, s_values):
    W = y1 - y0
    if e.get("kind") == "carriageway":
        lanes = max(1, int(e.get("lanes", 2)))
        WL = W / lanes
        ys = []
        for j in range(lanes):
            ys += [y0 + WL * j + WL / 6, y0 + WL * j + WL / 2, y0 + WL * j + 5 * WL / 6]
        ys = np.array(ys)
    else:
        n = n_trans(W)
        ys = y0 + W / n * (np.arange(n) + 0.5)
    SS, YY = np.meshgrid(s_values, ys, indexing="ij")
    return SS, YY, ys


def _quantities(route, lums, lum_s, SS, YY, fM, crowns, rt=None, lanes=None, y0=0.0, W=0.0,
                window=40.0, want_L=True, obs_s=None, obs_y=None):
    """E (on the surface) and L for a (ns, ny) grid.

    Without obs_s the observer moves with the point (60 m back, same lane);
    with obs_s / obs_y (arrays per point, or scalar y) the observer is fixed
    as in EN 13201-3 (60 m before the field, centre of a given lane)."""
    ns, ny = SS.shape
    E = np.zeros(ns * ny)
    L = np.zeros(ns * ny) if (want_L and rt is not None) else None
    s_flat = SS.ravel()
    y_flat = YY.ravel()
    P, _ = route.world(s_flat, y_flat)
    N = route.normal(s_flat, y_flat).reshape(-1, 3)
    Lpos = np.array([l.pos for l in lums]) if lums else np.zeros((0, 3))
    Hmax = max((l.pos[2] - l.pole[2] for l in lums), default=8.0)
    reach = 12 * Hmax + 5
    s0, s1 = float(s_flat.min()), float(s_flat.max())
    a = s0
    while a <= s1 + 1e-9:
        b = a + window
        m = (s_flat >= a) & (s_flat < b) if b <= s1 else (s_flat >= a)
        if np.any(m):
            sel = [i for i, ls in enumerate(lum_s) if a - reach <= ls <= b + reach]
            if sel:
                sub = [lums[i] for i in sel]
                Pm, Nm = P[m], N[m]
                I = group_intensities(sub, Pm)
                Lp = Lpos[sel]
                if crowns is not None and len(crowns):
                    cr = crowns[(crowns[:, 6] >= a - reach) & (crowns[:, 6] <= b + reach)]
                    if len(cr):
                        I = I * transmission(Lp, Pm, cr)
                V = Lp[:, None, :] - Pm[None, :, :]
                d2 = np.maximum((V ** 2).sum(-1), 1e-9)
                d = np.sqrt(d2)
                cos_i = np.clip((V * Nm[None, :, :]).sum(-1) / d, 0.0, 1.0)
                E[m] = fM * (I * cos_i / d2).sum(0)
                if L is not None:
                    # moving observer: 60 m back along the alignment, lane centre
                    sm = s_flat[m]
                    ym = y_flat[m]
                    if obs_s is not None:
                        so = np.asarray(obs_s, float).ravel()[m]
                        yo = np.broadcast_to(np.asarray(obs_y, float), s_flat.shape)[m] \
                            if np.ndim(obs_y) else np.full(m.sum(), float(obs_y))
                    else:
                        so = sm - 60.0
                        if lanes:
                            WL = W / lanes
                            lane = np.clip(((ym - y0) // WL).astype(int), 0, lanes - 1)
                            yo = y0 + (lane + 0.5) * WL
                        else:
                            yo = ym
                    O, _ = route.world(so, yo, dz=EYE)
                    H = np.maximum(cos_i * d, 1e-6)                    # height above the local plane
                    horiz = np.sqrt(np.maximum(d2 - H ** 2, 0.0))
                    tan_e = horiz / H
                    # project vectors on the local plane
                    vpl = V - (V * Nm[None]).sum(-1)[..., None] * Nm[None]       # P->L in plane
                    op = Pm - O
                    op = op - (op * Nm).sum(-1)[:, None] * Nm                    # O->P in plane
                    dot = (vpl * op[None]).sum(-1)
                    nrm = np.linalg.norm(vpl, axis=-1) * np.linalg.norm(op, axis=-1)[None]
                    cb = np.where(nrm > 1e-9, dot / np.maximum(nrm, 1e-12), 1.0)
                    beta = np.degrees(np.arccos(np.clip(cb, -1, 1)))
                    r = rt(tan_e, beta)
                    # every luminaire inside the r-table area (tan eps <= 12) counts: EN 13201-3
                    # 7.1.5 asks for *at least* 5H / 12H / 5H, see calc.luminance
                    ok = tan_e <= 12
                    L[m] = fM * np.where(ok, I * r / H ** 2, 0.0).sum(0)
        a = b
        if b > s1:
            break
    return E.reshape(ns, ny), (L.reshape(ns, ny) if L is not None else None)


def evaluate_route(route, poles, phot_lookup, fM=0.8, options=None):
    opt = dict(ds=None, trees=True, ti=True, display=True, display_ds=None, display_dt=0.5,
               age=23.0, max_display_rows=1600)
    opt.update(options or {})
    lums = make_luminaires(route, poles, phot_lookup)
    lum_s = [p["s"] for p in poles]
    crowns = crowns_array(route.trees()) if opt["trees"] else None
    Ltot = route.length
    el = route.section["elements"]
    edges = element_edges(el)
    ref = [p for p in poles if p["row"] == 0]
    spans = [(ref[i]["s"], ref[i + 1]["s"]) for i in range(len(ref) - 1)] or [(0.0, Ltot)]
    # EN 13201-3 style grids, span by span (N points per span, 3 per lane)
    from .calc import n_long
    s_list, span_of, span_start = [], [], []
    for k, (a, b) in enumerate(spans):
        N = n_long(max(b - a, 1.0))
        D = (b - a) / N
        for i in range(N):
            s_list.append(a + D / 2 + i * D)
            span_of.append(k)
            span_start.append(a)
    s_vals = np.array(s_list)
    # Ul only applies to long uninterrupted sections (EN 13201-2 Table 1 note a)
    feature_s = [float(c["s"]) for c in route.features.get("crossings", [])] + \
        [float(j["s"]) for j in route.features.get("junctions", [])]
    span_of = np.array(span_of)
    span_start = np.array(span_start)
    areas = []
    for ei, (e, (y0, y1)) in enumerate(zip(el, edges)):
        cls = (e.get("cls") or "").upper()
        if not cls or y1 - y0 <= 0:
            continue
        SS, YY, ys = _area_grid(route, e, y0, y1, s_vals)
        is_cw = e.get("kind") == "carriageway"
        rt = rtables.get(e.get("surface", "R3")) if is_cw else None
        lanes = max(1, int(e.get("lanes", 2))) if is_cw else None
        E, _ = _quantities(route, lums, lum_s, SS, YY, fM, crowns, want_L=False)
        Ls = []
        if is_cw:
            WL = (y1 - y0) / lanes
            OS = np.repeat((span_start - 60.0)[:, None], SS.shape[1], 1)
            for j in range(lanes):
                _, Lj = _quantities(route, lums, lum_s, SS, YY, fM, crowns, rt, lanes, y0, y1 - y0,
                                    obs_s=OS, obs_y=y0 + (j + 0.5) * WL)
                Ls.append(Lj)
        res = dict(index=ei, name=e.get("name") or e.get("kind", "").title(), kind=e.get("kind"),
                   cls=cls, y0=y0, y1=y1,
                   E_avg=float(E.mean()), E_min=float(E.min()), U0_E=float(E.min() / max(E.mean(), 1e-9)))
        if Ls:
            Lall = np.mean(Ls, axis=0)
            res.update(L_avg=float(min(L.mean() for L in Ls)), L_min=float(min(L.min() for L in Ls)),
                       U0_L=float(min(L.min() / max(L.mean(), 1e-9) for L in Ls)))
        sp_out = []
        for k, (a, b) in enumerate(spans):
            m = span_of == k
            if not np.any(m):
                continue
            Es = E[m]
            d = dict(s0=a, s1=b, E_avg=float(Es.mean()), E_min=float(Es.min()),
                     U0_E=float(Es.min() / max(Es.mean(), 1e-9)))
            if Ls:
                lav, u0s, uls = [], [], []
                for j, L in enumerate(Ls):
                    Lm = L[m]
                    lav.append(float(Lm.mean()))
                    u0s.append(float(Lm.min() / max(Lm.mean(), 1e-9)))
                    cl = Lm[:, 3 * j + 1]
                    uls.append(float(cl.min() / max(cl.max(), 1e-9)))
                d.update(L_avg=min(lav), U0_L=min(u0s), Ul=min(uls))
            interrupted = (k == 0 or k == len(spans) - 1 or any(
                a - (b - a) - 1.0 <= f <= b + (b - a) + 1.0 for f in feature_s))
            d["Ul_applies"] = not interrupted
            d["checks"] = _span_checks(d, cls, dict(e, apply_Ul=e.get("apply_Ul", True) and not interrupted))
            d["ok"] = all(c["ok"] for c in d["checks"])
            d["why"] = _diagnose(route, a, b, crowns, d)
            sp_out.append(d)
        res["spans"] = sp_out
        res["n_fail"] = sum(1 for d in sp_out if not d["ok"])
        if is_cw and opt["ti"]:
            res.update(_route_ti(route, lums, lum_s, ref, y0, y1, lanes, Ls[0] if Ls else None,
                                 s_vals, opt["age"], fM, Ls))
        areas.append(res)
    out = dict(length=Ltot, n_poles=len({(round(p["s"], 2), round(p["y"], 2)) for p in poles}),
               n_luminaires=len(poles), areas=areas,
               luminaires=[dict(l.to_dict(), id=p["id"], s=p["s"]) for l, p in zip(lums, poles)],
               trees=[dict(x=float(c[0]), y=float(c[1]), zc=float(c[2]), r=float(c[3]), rv=float(c[4]), s=float(c[6]))
                      for c in (crowns if crowns is not None else [])])
    if opt["display"]:
        out["display"] = _display(route, lums, lum_s, fM, crowns, opt)
    return out


def _span_checks(d, cls, e):
    k = classes.kind_of(cls)
    c = []
    if k == "M" and "L_avg" in d:
        L, U0, Ul, TI, REI = classes.M_CLASSES[cls]
        c.append(classes._crit("Average luminance", "L̄", d["L_avg"], L, ">=", "cd/m²", "ok", "too dark"))
        c.append(classes._crit("Overall uniformity", "Uo", d["U0_L"], U0, ">=", "", "ok", "dark patches"))
        if e.get("apply_Ul", True):
            c.append(classes._crit("Longitudinal uniformity", "Ul", d["Ul"], Ul, ">=", "", "ok", "banding"))
    elif k in ("C", "P"):
        q, v = classes.target_level(cls)
        c.append(classes._crit("Average illuminance", "Ē", d["E_avg"], v, ">=", "lx", "ok", "too dark"))
        if k == "C":
            c.append(classes._crit("Overall uniformity", "Uo", d["U0_E"], classes.C_CLASSES[cls][1], ">=", "",
                                   "ok", "uneven"))
        else:
            c.append(classes._crit("Minimum illuminance", "Emin", d["E_min"], classes.P_CLASSES[cls][1], ">=",
                                   "lx", "ok", "dark spot"))
    elif k == "RP8":
        q, v = classes.target_level(cls)
        if q == "L_avg" and "L_avg" in d:
            c.append(classes._crit("Average luminance", "Lavg", d["L_avg"], v, ">=", "cd/m²", "ok", "too dark"))
        elif q:
            c.append(classes._crit("Average illuminance", "Eavg", d["E_avg"], v, ">=", "lx", "ok", "too dark"))
    return [x for x in c if x]


def _diagnose(route, a, b, crowns, d):
    """Plain-language hints on why a span behaves differently from the straight design."""
    why = []
    mid = 0.5 * (a + b)
    _, _, _, k = route.al.at(mid)
    if abs(float(k)) > 1.0 / 1000:
        why.append("bend R = %.0f m" % (1 / abs(float(k))))
    for c in route.pr.curves():
        if abs(c["s"] - mid) < max(c["L"] / 2, 30):
            why.append("%s curve" % c["type"])
    g = float(route.pr.grade(mid)) * 100
    if abs(g) > 4:
        why.append("grade %.1f %%" % g)
    if crowns is not None and len(crowns):
        if np.any((crowns[:, 6] >= a - 5) & (crowns[:, 6] <= b + 5)):
            why.append("tree crowns")
    if b - a > 0:
        pass
    return why


def _route_ti(route, lums, lum_s, ref, y0, y1, lanes, L, s_vals, age, fM, Ls=None):
    W = y1 - y0
    WL = W / lanes
    worst = dict(TI=0.0, s=None, lane=None)
    for j in range(lanes):
        yo = y0 + (j + 0.5) * WL
        for p in ref[:-1]:
            H = p["H"]
            x0, screen = observer_start(H)
            s_eye = p["s"] + x0
            if s_eye < 0:
                continue
            eye, h = route.world(s_eye, yo, dz=EYE)
            g = float(route.pr.grade(s_eye))
            dirv = np.array([math.cos(float(h)), math.sin(float(h)), g])
            dirv /= np.linalg.norm(dirv)
            # line of sight 1 deg below the road direction
            horiz = np.array([dirv[0], dirv[1], 0.0])
            horiz /= np.linalg.norm(horiz)
            pitch = math.atan(g) - 1.0 * DEG
            sight = np.array([horiz[0] * math.cos(pitch), horiz[1] * math.cos(pitch), math.sin(pitch)])
            sel = [i for i, ls in enumerate(lum_s) if s_eye < ls <= s_eye + 500]
            if not sel:
                continue
            Lp = np.array([lums[i].pos for i in sel])
            v = Lp - eye
            dist = np.linalg.norm(v, axis=1)
            cos_t = np.clip(v @ sight / dist, -1, 1)
            th = np.degrees(np.arccos(cos_t))
            # screening plane: through the eye, transverse to the road, 20 deg above the road gradient
            along = v[:, 0] * horiz[0] + v[:, 1] * horiz[1]
            below = (v[:, 2] <= along * math.tan(math.atan(g) + 20.0 * DEG) + 1e-9) if screen else True
            ok = (along > 0) & below & (th > 0.1) & (th <= 60.0)
            if not np.any(ok):
                continue
            sub = [lums[sel[i]] for i in np.nonzero(ok)[0]]
            I = group_intensities(sub, np.array([eye]))[:, 0]
            Ek = I * cos_t[ok] / dist[ok] ** 2
            t = th[ok]
            lv = np.where(t > 1.5, 9.86 * (1 + (age / 66.4) ** 4) * Ek / t ** 2,
                          Ek * (10 / t ** 3 + 5 / t ** 2) * (1 + (age / 62.5) ** 4)).sum()
            # local initial luminance of the lane, 0..150 m ahead
            Lj = Ls[j] if Ls else L
            if Lj is not None:
                m = (s_vals >= p["s"]) & (s_vals <= p["s"] + 150)
                Li = float(Lj[m].mean()) / fM if np.any(m) else 1.0
            else:
                Li = 1.0
            ti = threshold_increment(float(lv), Li)
            if ti > worst["TI"]:
                worst = dict(TI=float(ti), s=float(s_eye), lane=j + 1)
    return dict(TI=worst["TI"], TI_at=worst["s"], TI_lane=worst["lane"])


def _display(route, lums, lum_s, fM, crowns, opt):
    """Surface meshes for the 3D view and the plan contours."""
    el = route.section["elements"]
    edges = element_edges(el)
    Ltot = route.length
    dsd = opt.get("display_ds") or max(0.5, Ltot / opt["max_display_rows"])
    s_vals = np.arange(0.0, Ltot + 1e-9, dsd)
    meshes = []
    for e, (y0, y1) in zip(el, edges):
        W = y1 - y0
        if W <= 0:
            continue
        n = max(2, int(math.ceil(W / opt["display_dt"])) + 1)
        ys = np.linspace(y0, y1, n)
        SS, YY = np.meshgrid(s_vals, ys, indexing="ij")
        is_cw = e.get("kind") == "carriageway"
        rt = rtables.get(e.get("surface", "R3")) if is_cw else None
        lanes = max(1, int(e.get("lanes", 2))) if is_cw else None
        E, L = _quantities(route, lums, lum_s, SS, YY, fM, crowns, rt, lanes, y0, W, want_L=is_cw)
        P, _ = route.world(SS.ravel(), YY.ravel())
        meshes.append(dict(kind=e.get("kind"), name=e.get("name") or e.get("kind"), y0=y0, y1=y1,
                           ns=len(s_vals), ny=n, s=s_vals.round(3).tolist(), y=ys.round(3).tolist(),
                           xyz=P.round(3).reshape(-1).tolist(),
                           E=E.round(3).reshape(-1).tolist(),
                           L=(L.round(4).reshape(-1).tolist() if L is not None else None)))
    return dict(meshes=meshes)


def refine(route, design, phot_lookup, fM=0.8, layout_options=None, max_iter=6, progress=None):
    """Lay out, evaluate and locally tighten the spacing where spans fail.

    Each iteration shortens the spacing by 10 % over every failing stretch
    (plus one span either side) until all spans pass or the iteration limit
    is reached.  Returns (poles, result, history).
    """
    from . import road as _road
    lo = dict(layout_options or {})
    local = list(lo.get("local", []))
    history = []
    poles = res = None
    for it in range(max_iter + 1):
        lo["local"] = local
        poles = _road.layout(route, design, lo)
        res = evaluate_route(route, poles, phot_lookup, fM, dict(display=False))
        fails = []
        for a in res["areas"]:
            for sp in a["spans"]:
                if not sp["ok"]:
                    fails.append((sp["s0"], sp["s1"], a["name"], [c["symbol"] for c in sp["checks"] if not c["ok"]]))
        history.append(dict(iteration=it, n_poles=len(poles), n_fail=len(fails),
                            fails=[dict(s0=f[0], s1=f[1], area=f[2], what=f[3]) for f in fails[:30]]))
        if progress:
            progress(min(1.0, (it + 1) / (max_iter + 1)))
        if not fails or it == max_iter:
            break
        S = float(design["S"])
        merged = []
        for a, b, _, _ in sorted(fails):
            a, b = a - S, b + S
            if merged and a <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        for a, b in merged:
            local.append(dict(s0=a, s1=b, factor=0.9))
    return poles, res, history
