# Street Lighting — road lighting design to EN 13201, CIE 140 and IES RP-8.
# Copyright (C) 2026 Emad Roshandel — GPL-3.0-or-later (see LICENSE)
"""JSON API used by both the local HTTP server and the in-browser (Pyodide)
engine.  Every call is stateless: the project is sent with each request;
parsed photometry is cached by content hash.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math

import numpy as np

from . import (APP_NAME, APP_VERSION, calc, classes, dxf, electrical, energy, geometry, importers,
               optimize, photometry, road, rtables, scheme, structural)

_PHOT_CACHE = {}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def clean(o):
    """Make results JSON-safe (numpy types, NaN, inf)."""
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, np.ndarray):
        return clean(o.tolist())
    if isinstance(o, (np.floating, float)):
        f = float(o)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return o


def _require(cond, msg):
    if not cond:
        raise ValueError(msg)


def build_phot(spec):
    """Photometry from a luminaire spec in the project."""
    key = hashlib.sha1(json.dumps(spec, sort_keys=True, default=str).encode()).hexdigest()
    if key in _PHOT_CACHE:
        return _PHOT_CACHE[key]
    src = spec.get("source", "generic")
    if src == "file":
        _require(spec.get("text"), "The luminaire file is empty.")
        ph = photometry.read_any(spec["text"], spec.get("filename", ""))
        if spec.get("lamp_flux_override"):
            ph = ph.scaled(float(spec["lamp_flux_override"]) / ph.lamp_flux)
        if spec.get("power_override"):
            ph.power = float(spec["power_override"])
    else:
        lt = spec.get("lamp_type", "LED")
        flux = float(spec.get("lamp_flux", 10000))
        _require(flux > 0, "Lamp flux must be positive.")
        ph = photometry.generic(spec.get("optic", "type3"), flux,
                                float(spec["power"]) if spec.get("power") else None, lt,
                                float(spec["lor"]) if spec.get("lor") else None,
                                spec.get("name"), float(spec["cct"]) if spec.get("cct") else None)
    if spec.get("name"):
        ph.name = spec["name"]
    if spec.get("weight"):
        ph.weight = float(spec["weight"])
    if spec.get("wind_area"):
        ph.wind_area = float(spec["wind_area"])
    if spec.get("rotate180"):
        ph.I = np.vstack([ph.I[(np.searchsorted(ph.C, (c + 180) % 360) % len(ph.C))] for c in ph.C])
        ph._cache = {}
    _PHOT_CACHE[key] = ph
    return ph


def lookup_for(project):
    lib = project.get("luminaires") or {}
    _require(lib, "Add at least one luminaire first.")
    cache = {}

    def get(k):
        if k not in cache:
            spec = lib.get(k)
            _require(spec is not None, "Unknown luminaire '%s'." % k)
            cache[k] = build_phot(spec)
        return cache[k]
    return get


def _mf(m):
    """CIE 154 maintenance factor from the project's maintenance inputs."""
    return energy.maintenance_factor(
        m.get("lamp", "LED"), m.get("llmf"), m.get("lsf"), m.get("lmf"), m.get("ip", "IP66"),
        m.get("pollution", "medium"), float(m.get("interval", 3.0)), float(m.get("hours", 4100)),
        (float(m.get("l_hours", 100000)), float(m.get("l_x", 0.9))), float(m.get("life", 100000)),
        relamp_years=m.get("relamp"), spot_replacement=m.get("spot", True) is not False)


def fM_of(project):
    m = project.get("maintenance") or {}
    if m.get("mode", "direct") == "direct":
        f = float(m.get("fM", 0.8))
    else:
        f = _mf(m)["fM"]
    _require(0.3 <= f <= 1.0, "The maintenance factor must lie between 0.3 and 1.0.")
    return f


def _section(project):
    sec = copy.deepcopy(project.get("section") or {})
    el = sec.get("elements") or []
    _require(el, "The cross-section has no strips.")
    for e in el:
        try:
            e["width"] = float(e.get("width") if e.get("width") is not None else 0)
        except (TypeError, ValueError):
            raise ValueError("Strip '%s' has no valid width." % (e.get("name") or e.get("kind", "?"))) from None
        _require(math.isfinite(e["width"]) and e["width"] >= 0, "A strip width cannot be negative or empty.")
        _require(e["width"] > 0 or not str(e.get("cls") or "").strip(),
                 "Strip '%s' has lighting class %s but zero width; give it a width or remove its class."
                 % (e.get("name") or e.get("kind", "?"), e.get("cls")))
        if e.get("kind") == "carriageway":
            e["lanes"] = int(e.get("lanes", 2) or 1)
            _require(e["lanes"] >= 1, "A carriageway needs at least one lane.")
    _require(any(e["width"] > 0 for e in el), "The cross-section has zero width.")
    # tree lines along the route are also used by the straight-road search
    # tree lines along most of the route also shape the straight-road search;
    # shorter tree stretches are handled by the route refinement
    r = project.get("route") or {}
    rt = r.get("features", {}).get("tree_lines") or []
    for t in rt:
        _require(float(t.get("crown_radius") or 0) > 0 and float(t.get("density") or 0) > 0,
                 "Each tree line needs a crown radius and a foliage density greater than zero.")
        _require(float(t.get("spacing") or 0) >= 1.0, "Trees in a line must be at least 1 m apart.")
        _require(float(t.get("height") or 0) > float(t.get("crown_base") or 0),
                 "A tree's top must be higher than the bottom of its crown.")
    mode = (project.get("search") or {}).get("trees_in_search", "auto")
    if rt and not sec.get("trees") and mode:
        L = float(r.get("length", 0) or 0) or _route_length_hint(r)
        cover = sum(max(0.0, float(t.get("s1", L)) - float(t.get("s0", 0))) for t in rt)
        if mode is True or mode == "always" or (L > 0 and cover / L >= 0.5):
            sec["trees"] = [dict(t, phase=0.0) for t in rt]
            sec["_trees_note"] = "Tree lines cover most of the route, so the search accounts for them."
    return sec


def _heights(hs):
    if not hs:
        return None
    out = [float(h) for h in hs]
    _require(all(2.0 <= h <= 30.0 for h in out), "Mounting heights to try must lie between 2 and 30 m.")
    return out


def _route_length_hint(r):
    if r.get("mode") == "segments":
        tot = 0.0
        for g in r.get("segments") or []:
            if g.get("type") == "arc":
                tot += float(g.get("length") or abs(float(g.get("angle", 0))) * math.pi / 180 * float(g["radius"]))
            else:
                tot += float(g.get("length", 0))
        return tot
    pts = r.get("points") or []
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))


def _route(project):
    r = project.get("route") or {}
    sec = _section(project)
    mode = r.get("mode", "straight")
    if mode == "straight":
        al = road.from_segments([dict(type="straight", length=float(r.get("length", 500)))])
    elif mode == "segments":
        _require(r.get("segments"), "Add at least one route segment.")
        al = road.from_segments(r["segments"], 0.0, 0.0, math.radians(float(r.get("heading", 0))))
    else:
        pts = r.get("points") or []
        _require(len(pts) >= 2, "Draw or import at least two route points.")
        al = road.from_polyline(pts, float(r.get("radius", 0) or 0) or None)
    _require(al.length > 1.0, "The route is too short.")
    prof = r.get("profile") or {}
    pv = prof.get("pvis") or []
    if not pv:
        pv = [(0.0, 0.0), (al.length, 0.0)]
    pr = road.Profile(pv, float(prof.get("crossfall", 0.0)))
    ref_y = r.get("ref_y")
    return road.Route(al, pr, sec, None if ref_y in (None, "") else float(ref_y), r.get("features") or {})


# ---------------------------------------------------------------------------
# endpoints
# ---------------------------------------------------------------------------
def health(_p):
    return dict(ok=True, app=APP_NAME, version=APP_VERSION)


def meta(_p):
    return clean(dict(
        app=APP_NAME, version=APP_VERSION, classes=classes.all_classes(),
        selection={k: [dict(key=a, label=b, options=[dict(key=o[0], label=o[1], w=o[2]) for o in c])
                       for a, b, c in v] for k, v in classes.SELECTION.items()},
        road_types=[dict(key=a, label=b, en=c, rp8=d, speed=e) for a, b, c, d, e in classes.ROAD_TYPES],
        lamp_types={k: v for k, v in photometry.LAMP_TYPES.items()},
        optics={k: v["label"] for k, v in photometry.OPTICS.items()},
        surfaces={k: v for k, v in rtables.DESCRIPTORS.items()},
        arrangements=optimize.ARRANGEMENTS,
        terrain={k: dict(kr=v[0], z0=v[1], zmin=v[2], label=v[3]) for k, v in structural.TERRAIN.items()},
        electrical_defaults=electrical.DEFAULT, cost_defaults=optimize.DEFAULT_COSTS,
        cable_sizes=electrical.SIZES))


def luminaire_info(p):
    spec = p.get("spec") or p
    ph = build_phot(spec)
    d = ph.to_dict()
    d["polar"] = ph.polar((0, 90, 180, 270))
    d["polar15"] = ph.polar((15, 165, 75, 105))
    d["isocandela"] = ph.isocandela()
    tilt = float(p.get("tilt", 0.0))
    d["gstar"] = geometry.installed_intensity_class(ph, tilt)
    d["glare"] = geometry.glare_index(ph)
    d["street_side"] = ph.street_side()
    d["symmetric_c90"] = ph.symmetric_c90()
    return clean(d)


def select_class(p):
    return clean(classes.select_class(p.get("series", "M"), p.get("answers", {})))


def maintenance(p):
    return clean(_mf(p))


def optimize_ep(p):
    pr = p.get("project") or p
    sec = _section(pr)
    look = lookup_for(pr)
    fM = fM_of(pr)
    sc = pr.get("search") or {}
    keys = sc.get("phots") or list((pr.get("luminaires") or {}).keys())
    lib = pr.get("luminaires") or {}
    fmin = 1.0
    dims = [float(lib[k].get("dim_min", 0.3)) if lib[k].get("dimmable", True) else 1.0 for k in keys]
    fmin = min(dims) if dims else 1.0
    res = optimize.search(
        sec, keys, look, fM,
        rule=sc.get("rule"),
        heights=_heights(sc.get("heights")),
        overhangs=[float(h) for h in sc["overhangs"]] if sc.get("overhangs") else None,
        tilts=[float(h) for h in sc["tilts"]] if sc.get("tilts") else None,
        arrangements=sc.get("arrangements") or None,
        S_range=tuple(sc["S_range"]) if sc.get("S_range") else None,
        costs=pr.get("costs"), dimming=(fmin, 1.0), setback=float(sc.get("setback", 0.8)),
        top=int(sc.get("top", 12)), mode="full" if sc.get("full") else "auto")
    for c in res["candidates"]:
        c["lines"] = res["lines"]
        c["phot_name"] = look(c["phot"]).name
    out = dict(res, fM=fM)
    if res["candidates"]:
        best = res["candidates"][0]
        out["best"] = _finalize(pr, sec, best, look, fM)
    else:
        out["advice"] = _no_solution_advice(sec, keys, look, fM)
    return clean(out)


def _no_solution_advice(sec, keys, look, fM):
    tips = ["No arrangement met every requirement with the selected luminaire(s)."]
    tot = max(look(k).luminaire_flux for k in keys)
    tips.append("The brightest luminaire gives %.0f lm; try a higher lumen package or a second "
                "luminaire type." % tot)
    tips.append("Check that the classes are realistic for the road (a lower M class, or C/P for "
                "slow streets) and widen the height / spacing ranges.")
    if sec.get("trees"):
        tips.append("Tree crowns block much of the light: consider pruning, mounting below the crowns "
                    "or a catenary / centre-line system.")
    return tips


def _finalize(pr, sec, cand, look, fM):
    res = optimize.finalize(sec, cand, look, fM, (pr.get("search") or {}).get("rule"))
    ph = look(cand["phot"])
    res["gstar"] = geometry.installed_intensity_class(ph, cand["tilt"])
    res["glare"] = geometry.glare_index(ph)
    # energy for the representative section
    S = cand["S"]
    areas = [dict(E_avg=a["E_avg"], area=a["width"] * S) for a in res["areas"] if a["cls"]]
    P = len(cand["rows"]) * ph.power * (0.08 + 0.92 * cand["f"])
    en = pr.get("energy") or {}
    prof = en.get("profile") or energy.profile_from(en.get("kind", "full"), float(en.get("hours", 4100)),
                                                     float(en.get("reduce_from", 0.5)), float(en.get("level", 0.5)))
    res["energy"] = energy.pdi_aeci(areas, P, prof, float(en.get("standby_W", 0.0)) * len(cand["rows"]))
    res["candidate"] = cand
    return res


def evaluate_ep(p):
    pr = p["project"]
    cand = p["candidate"]
    sec = _section(pr)
    look = lookup_for(pr)
    fM = fM_of(pr)
    return clean(_finalize(pr, sec, cand, look, fM))


def manual_ep(p):
    """Evaluate a user-defined geometry (no search)."""
    pr = p["project"]
    sec = _section(pr)
    look = lookup_for(pr)
    fM = fM_of(pr)
    m = p["manual"]
    lines = optimize.pole_lines(sec, float(m.get("setback", 0.8)))
    ph = look(m["phot"])
    nu = 0.0 if ph.street_side() > 0 else 180.0
    rows = optimize.make_rows(m["arrangement"], lines, float(m["H"]), float(m["overhang"]),
                              float(m["tilt"]), m["phot"], nu, float(m.get("flux", 1.0)))
    _require(rows, "This arrangement is not possible on this cross-section.")
    cand = dict(phot=m["phot"], arrangement=m["arrangement"], label=optimize.ARRANGEMENTS.get(m["arrangement"]),
                H=float(m["H"]), overhang=float(m["overhang"]), tilt=float(m["tilt"]), S=float(m["S"]),
                f=float(m.get("flux", 1.0)), need=None, rows=rows, lines=lines, phot_name=ph.name,
                dimmable=True)
    cand.update(optimize.candidate_cost(cand, pr.get("costs"), look))
    return clean(_finalize(pr, sec, cand, look, fM))


def _route_ti_excess(res):
    worst = 0.0
    for a in res["areas"]:
        if classes.kind_of(a["cls"]) == "M" and a.get("TI") is not None:
            worst = max(worst, a["TI"] - classes.M_CLASSES[a["cls"]][3])
    return worst


def route_geometry(p):
    """Alignment, profile, edges and topology findings — no lighting."""
    pr = p["project"]
    rt = _route(pr)
    trees = rt.trees()
    return clean(dict(alignment=rt.al.to_dict(1.0), profile=dict(pvis=rt.pr.pvis, crossfall=rt.pr.crossfall,
                                                               curves=rt.pr.curves()),
                      topology=rt.describe_topology(), ref_y=rt.ref_y, width=rt.W, length=rt.length,
                      edges=calc.element_edges(rt.section["elements"]),
                      trees=[dict(x=t["x"], y=t["yw"], r=t["r"], s=t["s"]) for t in trees]))


def route_ep(p):
    pr = p["project"]
    cand = p["candidate"]
    look = lookup_for(pr)
    fM = fM_of(pr)
    rt = _route(pr)
    lo = dict((pr.get("route") or {}).get("layout") or {})
    lo.setdefault("margin", 0.95)
    if p.get("refine", True):
        poles, res, hist = scheme.refine(rt, cand, look, fM, lo, int(lo.get("max_iter", 6)))
    else:
        poles = road.layout(rt, cand, lo)
        hist = []
    res = scheme.evaluate_route(rt, poles, look, fM, dict(display=False))
    # glare along the route (crests, bends): try less tilt before reporting a failure
    adjust = []
    if p.get("auto_tilt", True) and _route_ti_excess(res) > 0:
        for new_tilt in sorted({max(0.0, cand["tilt"] - 5.0), 0.0}, reverse=True):
            if new_tilt >= cand["tilt"]:
                continue
            c2 = dict(cand, tilt=new_tilt, rows=[dict(r, tilt=new_tilt) for r in cand["rows"]])
            p2, r2, h2 = scheme.refine(rt, c2, look, fM, lo, int(lo.get("max_iter", 6)))
            r2 = scheme.evaluate_route(rt, p2, look, fM, dict(display=False))
            if _route_ti_excess(r2) <= 0 and sum(a["n_fail"] for a in r2["areas"]) <= sum(a["n_fail"] for a in res["areas"]):
                adjust.append("Tilt reduced from %.0f° to %.0f° to keep the threshold increment within the "
                              "limit along the route." % (cand["tilt"], new_tilt))
                poles, hist = p2, hist + [dict(h, iteration="tilt %.0f°: %s" % (new_tilt, h["iteration"])) for h in h2]
                break
    res = scheme.evaluate_route(rt, poles, look, fM, dict(display=True))
    out = dict(result=res, poles=poles, history=hist, topology=rt.describe_topology(), adjustments=adjust,
               alignment=rt.al.to_dict(), profile=dict(pvis=rt.pr.pvis, crossfall=rt.pr.crossfall,
                                                       curves=rt.pr.curves()),
               ref_y=rt.ref_y, width=rt.W,
               edges=calc.element_edges(rt.section["elements"]))
    # route-level checks summary
    checks = []
    for a in res["areas"]:
        k = classes.kind_of(a["cls"])
        if a.get("TI") is not None and k == "M":
            lim = classes.M_CLASSES[a["cls"]][3]
            checks.append(dict(area=a["name"], name="Threshold increment along the route", value=a["TI"],
                               req=lim, ok=a["TI"] <= lim,
                               reason=("glare acceptable" if a["TI"] <= lim else
                                       "glare too high near ch %.0f — luminaires seen at low angles "
                                       "(crest / bend): choose a G*4..G*6 optic or reduce tilt" % (a.get("TI_at") or 0))))
        checks.append(dict(area=a["name"], name="Spans complying", value=len(a["spans"]) - a["n_fail"],
                           req=len(a["spans"]), ok=a["n_fail"] == 0,
                           reason="all spans comply" if a["n_fail"] == 0 else "%d span(s) fail" % a["n_fail"]))
    bad = [q for q in poles if q.get("conflict")]
    checks.append(dict(area="Route", name="Column positions", value=len(poles) - len(bad), req=len(poles),
                       ok=not bad,
                       reason="every column stands where it is allowed" if not bad else
                       "; ".join("%s at ch %.0f %s" % (q["id"], q["s"], q["conflict"]) for q in bad[:6])
                       + ("; …" if len(bad) > 6 else "")))
    out["checks"] = checks
    out["ok"] = all(c["ok"] for c in checks)
    # energy for the whole route
    W = sum(look(q["phot"]).power * (0.08 + 0.92 * float(q.get("flux", 1.0))) for q in poles)
    areas = [dict(E_avg=a["E_avg"], area=(a["y1"] - a["y0"]) * rt.length) for a in res["areas"]]
    en = pr.get("energy") or {}
    prof = en.get("profile") or energy.profile_from(en.get("kind", "full"), float(en.get("hours", 4100)),
                                                     float(en.get("reduce_from", 0.5)), float(en.get("level", 0.5)))
    out["energy"] = energy.summary(W, areas, prof, float(en.get("standby_W", 0.0)) * len(poles),
                                   float(en.get("price", 0.12)), float(en.get("co2", 0.55)),
                                   int(en.get("years", 20)), float(en.get("discount", 0.06)))
    return clean(out)


def electrical_ep(p):
    pr = p["project"]
    look = lookup_for(pr)
    poles = p["poles"]
    _require(poles, "Lay out the poles first (Route step).")
    power = {k: look(k).power for k in {q["phot"] for q in poles}}
    return clean(electrical.design(poles, power, pr.get("electrical")))


def structural_ep(p):
    pr = p.get("project") or {}
    look = lookup_for(pr) if pr.get("luminaires") else None
    H = float(p["H"])
    oh = float(p.get("overhang", 0.0))
    nh = int(p.get("n_heads", 1))
    w, a = 10.0, 0.12
    if look and p.get("phot"):
        ph = look(p["phot"])
        w, a = ph.weight, ph.wind_area
    st = pr.get("structural") or {}
    return clean(structural.design_pole(H, oh, float(p.get("weight", w)), float(p.get("wind_area", a)), nh,
                                        st.get("wind"), st.get("soil")))


def import_route(p):
    r = importers.read_any(p["text"], p.get("filename", ""))
    pts = r["points"]
    if p.get("simplify", True) and len(pts) > 200:
        pts = importers.simplify(pts, float(p.get("tolerance", 0.5)))
    # shift to a local origin
    x0, y0 = pts[0][0], pts[0][1]
    r["offset"] = [x0, y0]
    r["points"] = [[q[0] - x0, q[1] - y0] + q[2:3] for q in pts]
    if r.get("has_z"):
        al = road.from_polyline([q[:2] for q in r["points"]], float(p.get("radius", 0) or 0) or None)
        r["profile"] = importers.profile_from_points(r["points"], al)
    return clean(r)


def import_profile(p):
    return clean(importers.read_profile_csv(p["text"]))


def export_dxf_route(p):
    pr = p["project"]
    rt = _route(pr)
    info = p.get("info") or ["%s %s" % (APP_NAME, APP_VERSION)]
    s = dxf.route_drawing(rt, p["poles"], p.get("result"), p.get("electrical"),
                          p.get("title", pr.get("name", "Street lighting layout")), info,
                          p.get("quantity", "E"))
    return dict(text=s, filename=(pr.get("name") or "street_lighting").replace(" ", "_") + "_layout.dxf")


def export_dxf_section(p):
    pr = p["project"]
    sec = _section(pr)
    s = dxf.section_drawing(sec, p["candidate"], p["result"], p.get("title", pr.get("name", "Typical section")),
                            p.get("info"))
    return dict(text=s, filename=(pr.get("name") or "street_lighting").replace(" ", "_") + "_section.dxf")


def export_ldt(p):
    ph = build_phot(p["spec"])
    return dict(text=photometry.write_ldt(ph), filename=(ph.name or "luminaire")[:40].replace(" ", "_") + ".ldt")


def rtable_ep(p):
    return clean(rtables.get(p.get("name", "R3")).to_dict())


ROUTES = {
    "/api/health": health,
    "/api/meta": meta,
    "/api/luminaire": luminaire_info,
    "/api/class/select": select_class,
    "/api/maintenance": maintenance,
    "/api/optimize": optimize_ep,
    "/api/evaluate": evaluate_ep,
    "/api/manual": manual_ep,
    "/api/route": route_ep,
    "/api/route/geometry": route_geometry,
    "/api/electrical": electrical_ep,
    "/api/structural": structural_ep,
    "/api/import/route": import_route,
    "/api/import/profile": import_profile,
    "/api/export/dxf_route": export_dxf_route,
    "/api/export/dxf_section": export_dxf_section,
    "/api/export/ldt": export_ldt,
    "/api/rtable": rtable_ep,
}


def dispatch(path, payload):
    fn = ROUTES[path]
    return fn(payload or {})
