# Street Lighting — road lighting design to EN 13201, CIE 140 and IES RP-8.
# Copyright (C) 2026 Emad Roshandel — GPL-3.0-or-later (see LICENSE)
"""Search for the pole height, spacing, arrangement, overhang, tilt and
light output that satisfy every lighting class of the cross-section at the
lowest life-cycle cost.

Key facts used to keep the search fast and exact:

* luminance and illuminance scale linearly with luminaire flux, so the
  uniformities (Uo, Ul, Emin/Eavg, REI) depend only on the geometry and the
  required flux factor f follows directly from the levels;
* the threshold increment scales as f^0.2 (Lv ~ f, Li^0.8 ~ f^0.8);
* uniformity falls as the spacing grows, so the largest feasible spacing is
  found by bisection for every geometry and confirmed by a full evaluation.
"""
from __future__ import annotations

import itertools
import math


from . import calc, classes
from .calc import element_edges

PRESETS_H = [4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 14.0, 16.0]


# ---------------------------------------------------------------------------
# candidate arrangements from the cross-section
# ---------------------------------------------------------------------------
def pole_lines(section, setback=0.8):
    """Possible pole lines (y positions) next to every carriageway.

    Returns a dict: 'left' / 'right' (outer edges of the road),
    'median' (centre of a median between carriageways) where present.
    """
    el = section["elements"]
    edges = element_edges(el)
    cw = [i for i, e in enumerate(el) if e.get("kind") == "carriageway"]
    W = calc.total_width(el)
    out = {}
    if not cw:
        # pedestrian-only road: poles at the outer edges
        out["left"] = dict(y=min(setback, W / 2), face=+1, edge=0.0)
        out["right"] = dict(y=max(W - setback, W / 2), face=-1, edge=W)
        return out
    first, last = cw[0], cw[-1]
    yl = edges[first][0]
    yr = edges[last][1]
    # left: the pole sits `setback` outside the kerb if there is room, else at the edge
    room_l = yl
    out["left"] = dict(y=yl - min(setback, room_l) if room_l > 0 else yl - setback, face=+1, edge=yl)
    room_r = W - yr
    out["right"] = dict(y=yr + min(setback, room_r) if room_r > 0 else yr + setback, face=-1, edge=yr)
    for a, b in zip(cw, cw[1:]):
        mid = [i for i in range(a + 1, b)]
        if mid:
            y0 = edges[mid[0]][0]
            y1 = edges[mid[-1]][1]
            out["median"] = dict(y=0.5 * (y0 + y1), face=0, edge=None, width=y1 - y0)
    return out


ARRANGEMENTS = {
    "single_left": "Single-sided (side A)",
    "single_right": "Single-sided (side B)",
    "opposite": "Opposite (both sides)",
    "staggered": "Staggered",
    "twin_central": "Twin central (median)",
    "twin_central_opposite": "Twin central + opposite",
    "central": "Central single row (median)",
}


def make_rows(arr, lines, H, overhang, tilt, phot_key, nu_offset=0.0, flux=1.0):
    rows = []

    def row(line, face, phase=0.0, oh=overhang):
        return dict(y=line["y"], side=face, overhang=oh, height=H, tilt=tilt, phase=phase,
                    phot=phot_key, nu_offset=nu_offset, flux=flux)

    L, R, M = lines.get("left"), lines.get("right"), lines.get("median")
    if arr == "single_left" and L:
        rows.append(row(L, +1))
    elif arr == "single_right" and R:
        rows.append(row(R, -1))
    elif arr == "opposite" and L and R:
        rows += [row(L, +1), row(R, -1)]
    elif arr == "staggered" and L and R:
        rows += [row(L, +1), row(R, -1, 0.5)]
    elif arr in ("twin_central", "twin_central_opposite") and M:
        rows += [row(M, -1), row(M, +1)]
        if arr == "twin_central_opposite" and L and R:
            rows += [row(L, +1), row(R, -1)]
    elif arr == "central" and M:
        rows.append(row(M, +1, 0.0, 0.0))
    return rows


def applicable_arrangements(section):
    el = section["elements"]
    cw = [e for e in el if e.get("kind") == "carriageway"]
    W = sum(e["width"] for e in cw) if cw else calc.total_width(el)
    lines = pole_lines(section)
    out = ["single_left", "single_right"]
    if W > 7.0 or not cw:
        out += ["staggered", "opposite"]
    else:
        out += ["staggered"]
    if "median" in lines:
        out += ["twin_central"]
        if W > 15:
            out += ["twin_central_opposite"]
    return out


# ---------------------------------------------------------------------------
# economic model
# ---------------------------------------------------------------------------
DEFAULT_COSTS = dict(
    currency="USD",
    pole_base=250.0, pole_per_m=60.0, arm_per_m=60.0, foundation=180.0,
    luminaire={},              # key -> unit price; default from power
    luminaire_per_w=3.0, luminaire_min=150.0,
    cable_per_m=8.0, trench_per_m=15.0, install_per_pole=120.0,
    energy_price=0.12, hours=4100.0, years=20, discount=0.06,
    maint_per_lum_year=8.0,
)


def annuity(rate, years):
    if rate <= 0:
        return float(years)
    return (1 - (1 + rate) ** -years) / rate


def candidate_cost(cand, costs, phot_lookup, length=1000.0):
    c = dict(DEFAULT_COSTS)
    c.update(costs or {})
    S = cand["S"]
    rows = cand["rows"]
    n_per_span_lum = len(rows)
    ys = {round(r["y"], 3) for r in rows}
    n_per_span_pole = len(ys)
    n_lum = length / S * n_per_span_lum
    n_pole = length / S * n_per_span_pole
    H = rows[0]["height"]
    oh = max(r["overhang"] for r in rows)
    pole = c["pole_base"] + c["pole_per_m"] * H + c["arm_per_m"] * oh + c["foundation"] + c["install_per_pole"]
    ph = phot_lookup(rows[0]["phot"])
    lum_price = c["luminaire"].get(rows[0]["phot"]) or max(c["luminaire_min"], c["luminaire_per_w"] * ph.power)
    f = cand["f"]
    p_lum = ph.power * (0.08 + 0.92 * f) if cand.get("dimmable", True) else ph.power
    kw = n_lum * p_lum / 1000.0
    energy_year = kw * c["hours"]
    lines = len(ys) if len(ys) > 1 and min(ys) < max(ys) - 3 else 1
    cable = length * (c["cable_per_m"] + c["trench_per_m"]) * lines
    capex = n_pole * pole + n_lum * lum_price + cable
    opex = energy_year * c["energy_price"] + n_lum * c["maint_per_lum_year"]
    npv = capex + opex * annuity(c["discount"], c["years"])
    return dict(n_poles_km=n_pole, n_lum_km=n_lum, kw_km=kw, kwh_year_km=energy_year,
                capex_km=capex, opex_km=opex, npv_km=npv, lum_power=p_lum)


# ---------------------------------------------------------------------------
# evaluation of one geometry
# ---------------------------------------------------------------------------
def _levels(section, res, rule):
    """Flux factor needed by every class, and the cap from upper limits."""
    need, cap = 1e-9, float("inf")
    notes = []
    has_traffic = any(a["kind"] == "carriageway" and a["cls"] for a in res["areas"])
    for a in res["areas"]:
        cls = a["cls"]
        if not cls:
            continue
        q, val = classes.target_level(cls, a.get("surface", "R3"))
        if q is None:
            continue
        got = a.get(q, 0.0)
        if got <= 0:
            return float("inf"), 0.0, ["no light reaches %s" % a["name"]]
        need = max(need, val / got)
        k = classes.kind_of(cls)
        if k == "P":
            Pc = classes.P_CLASSES[cls.upper()]
            if Pc[1] and a["E_min"] > 0:
                need = max(need, Pc[1] / a["E_min"])
            if rule.get("facial"):
                if Pc[2] and a["Ev_min"] > 0:
                    need = max(need, Pc[2] / a["Ev_min"])
                if Pc[3] and a["Esc_min"] > 0:
                    need = max(need, Pc[3] / a["Esc_min"])
            # upper limit only where the P area governs the design
            if rule.get("p_upper", True) and not (has_traffic and a["kind"] != "carriageway"):
                cap = min(cap, 1.5 * Pc[0] / got)
        if k == "RP8":
            n = cls[4:].strip()
            if n in classes.RP8_WALKWAY and a["Ev_min"] > 0:
                need = max(need, classes.RP8_WALKWAY[n][1] / a["Ev_min"])
    return need, cap, notes


def _uniformity_ok(res, rule):
    """Flux-independent criteria (uniformities, REI)."""
    fails = []
    for a in res["areas"]:
        cls = a["cls"].upper() if a["cls"] else ""
        k = classes.kind_of(cls)
        if k == "M" and "U0_L" in a:
            L, U0, Ul, TI, REI = classes.M_CLASSES[cls]
            if a["U0_L"] < U0 - 1e-9:
                fails.append("Uo")
            if rule.get("apply_Ul", True) and a["Ul"] < Ul - 1e-9:
                fails.append("Ul")
            rei = (a.get("REI") or {}).get("value")
            if rule.get("apply_REI", True) and rei is not None and rei < REI - 1e-9:
                fails.append("REI")
        elif k == "C":
            if a["U0_E"] < classes.C_CLASSES[cls][1] - 1e-9:
                fails.append("Uo")
        elif k == "HS" and classes.HS_CLASSES[cls][0]:
            if a["U0_hs"] < classes.HS_CLASSES[cls][1] - 1e-9:
                fails.append("Uo_hs")
        elif k == "RP8":
            n = a["cls"][4:].strip()
            if n in classes.RP8_LUMINANCE and "observers" in a:
                L, r1, r2, rv = classes.RP8_LUMINANCE[n]
                lmin = min(o["L_min"] for o in a["observers"])
                lmax = max(o["L_max"] for o in a["observers"])
                if lmin <= 0 or a["L_avg"] / lmin > r1 or lmax / lmin > r2:
                    fails.append("uniformity")
            elif n in classes.RP8_ILLUMINANCE or n in classes.RP8_WALKWAY:
                r = (classes.RP8_ILLUMINANCE.get(n) or classes.RP8_WALKWAY.get(n))[1 if n in classes.RP8_ILLUMINANCE else 2]
                if a["E_min"] <= 0 or a["E_avg"] / a["E_min"] > r:
                    fails.append("uniformity")
    return fails


def _ti_ok(res, f, rule):
    worst = 0.0
    for a in res["areas"]:
        cls = (a["cls"] or "").upper()
        k = classes.kind_of(cls)
        ti = a.get("TI")
        if ti is None:
            continue
        tif = ti * f ** 0.2
        lim = None
        if k == "M":
            lim = classes.M_CLASSES[cls][3]
        elif k == "C":
            lim = classes.C_CLASSES[cls][2]
        elif k == "P" and rule.get("apply_TI_P"):
            lim = classes.P_CLASSES[cls][4]
        elif k == "RP8":
            n = a["cls"][4:].strip()
            if n in classes.RP8_LUMINANCE and a.get("L_avg"):
                ratio = a["Lv"] * f / (a["L_avg"] * f / res["fM"])
                if ratio > classes.RP8_LUMINANCE[n][3]:
                    return False, ratio
                continue
        if lim is not None:
            worst = max(worst, tif / lim)
            if tif > lim + 1e-9:
                return False, tif
    return True, worst


def evaluate_geometry(section, rows, S, phot_lookup, fM, rule, with_ti=False):
    res = calc.evaluate(section, rows, S, phot_lookup, fM,
                        options=dict(display=False, ti=with_ti, vertical=bool(rule.get("facial"))))
    fails = _uniformity_ok(res, rule)
    need, cap, notes = _levels(section, res, rule)
    return res, fails, need, cap


def search(section, phot_keys, phot_lookup, fM=0.8, rule=None, heights=None, overhangs=None,
           tilts=None, arrangements=None, S_range=None, costs=None, dimming=(0.3, 1.0),
           top=12, progress=None, setback=0.8, max_evals=6000, mode="auto", screen_keep=3):
    """Exhaustive geometry search with spacing bisection.

    Returns a list of feasible candidates sorted by life-cycle cost, each
    with the full EN 13201-3 evaluation at the chosen spacing.

    Every luminaire gets its own budget of max_evals calculations.  With more
    than screen_keep luminaires and mode "auto", a quick pass first ranks all of
    them on a coarse grid (3 heights, 2 arm lengths, one tilt, 1 m spacing
    steps) and only the screen_keep cheapest are searched in full; mode "full"
    searches every luminaire in full (slower).
    """
    base = dict(apply_Ul=True, apply_REI=True, p_upper=True, apply_TI_P=False, facial=False)
    base.update(_rule_from_section(section))
    base.update(rule or {})
    rule = base
    if isinstance(phot_keys, str):
        phot_keys = [phot_keys]
    lines = pole_lines(section, setback)
    arrs = arrangements or applicable_arrangements(section)
    if (arrangements is None and _mirror_symmetric(section) and "single_right" in arrs
            and all(phot_lookup(k).symmetric_c90() for k in phot_keys)):
        arrs = [a for a in arrs if a != "single_right"]
    cw_w = sum(e["width"] for e in section["elements"] if e.get("kind") == "carriageway") or \
        calc.total_width(section["elements"])
    if heights is None:
        hmin = 4.0 if cw_w < 6 else 6.0 if cw_w < 9 else 8.0
        hmax = 8.0 if cw_w < 6 else 12.0 if cw_w < 15 else 16.0
        heights = [h for h in PRESETS_H if hmin <= h <= hmax]
    if overhangs is None:
        overhangs = [0.0, 0.5, 1.0, 1.5, 2.0]
    tree_notes = []
    trees = section.get("trees") or []
    if trees:
        # "the art": try luminaires below the crowns, above them, or on arms reaching past them
        hs, ohs = set(heights), set(overhangs)
        for tl in trees:
            base, ctop, r = float(tl.get("crown_base", 3)), float(tl.get("height", 8)), float(tl.get("crown_radius", 2.5))
            hu = math.floor((base - 0.4) * 2) / 2.0
            if hu >= 3.5:
                hs.add(hu)
                tree_notes.append("mounting below the crowns (H = %.1f m) is tried" % hu)
            ha = math.ceil(ctop + 1.0)
            if ha <= 16:
                hs.add(float(ha))
                tree_notes.append("mounting above the crowns (H = %.0f m) is tried" % ha)
            for key, ln in lines.items():
                if ln.get("face"):
                    d = (float(tl["y"]) - ln["y"]) * ln["face"]
                    if 0 <= d < r + 4.0:
                        need = round(d + r + 0.3, 1)
                        if need <= 4.0:
                            ohs.add(need)
                            tree_notes.append("arms of %.1f m reaching past the crowns are tried" % need)
        heights, overhangs = sorted(hs), sorted(ohs)
    if tilts is None:
        tilts = [0.0, 5.0, 10.0]
    fmin, fmax = dimming
    n_eval = [0]

    def trial(pk, arr, H, oh, tilt, tol=0.25):
        """Longest compliant spacing for one geometry, or None."""
        ph = phot_lookup(pk)
        nu_off = 0.0 if ph.street_side() > 0 else 180.0
        rows = make_rows(arr, lines, H, oh, tilt, pk, nu_off)
        if not rows:
            return None
        if trees and _head_in_crown(rows, trees):
            return None
        Smin, Smax = S_range or (max(2.0 * H, 8.0), min(6.0 * H, 70.0))
        # coarse feasibility at the shortest spacing
        res, fails, need, cap = evaluate_geometry(section, rows, Smin, phot_lookup, fM, rule)
        n_eval[0] += 1
        if fails or need > fmax * (1.0 + 1e-9) or need > cap:
            return None
        lo, hi = Smin, Smax
        res_hi, fails_hi, need_hi, cap_hi = evaluate_geometry(section, rows, hi, phot_lookup, fM, rule)
        n_eval[0] += 1
        if not fails_hi and need_hi <= fmax and need_hi <= cap_hi:
            lo = hi
        else:
            for _ in range(9):
                mid = 0.5 * (lo + hi)
                r_, f_, n_, c_ = evaluate_geometry(section, rows, mid, phot_lookup, fM, rule)
                n_eval[0] += 1
                if not f_ and n_ <= fmax and n_ <= c_:
                    lo = mid
                else:
                    hi = mid
                if hi - lo < tol:
                    break
        S = math.floor(lo * 4) / 4.0
        res, fails, need, cap = evaluate_geometry(section, rows, S, phot_lookup, fM, rule, with_ti=True)
        n_eval[0] += 1
        f = min(max(need, fmin), fmax)
        if fails or need > fmax + 1e-9 or f > cap + 1e-9:
            return None
        ok, ti_worst = _ti_ok(res, f, rule)
        if not ok:
            return None
        cand = dict(phot=pk, arrangement=arr, label=ARRANGEMENTS.get(arr, arr), H=H, overhang=oh,
                    tilt=tilt, S=S, f=f, need=need, rows=[dict(r, flux=f) for r in rows],
                    ti_ratio=ti_worst, dimmable=fmin < 1.0)
        cand.update(candidate_cost(cand, costs, phot_lookup))
        return cand

    def run_grid(keys, hs, ohs, tls, budget, tol, p0, p1):
        """Every geometry for each luminaire, each luminaire with its own calculation budget."""
        out, skipped = [], []
        per = list(itertools.product(arrs, hs, ohs, tls))
        total = max(len(keys) * len(per), 1)
        for ki, pk in enumerate(keys):
            start = n_eval[0]
            for gi, (arr, H, oh, tilt) in enumerate(per):
                if progress:
                    progress(p0 + (p1 - p0) * (ki * len(per) + gi) / total)
                if n_eval[0] - start > budget:
                    skipped.append(pk)
                    break
                c = trial(pk, arr, H, oh, tilt, tol)
                if c:
                    out.append(c)
        return out, skipped

    def spread(vals, n):
        """n values spread over a sorted list (always its ends)."""
        vals = sorted(vals)
        if len(vals) <= n:
            return vals
        return sorted({vals[round(i * (len(vals) - 1) / (n - 1))] for i in range(n)})

    keys = list(dict.fromkeys(phot_keys))
    screening = []
    full_keys = keys
    if mode != "full" and len(keys) > screen_keep:
        # 1) quick pass: every luminaire on a coarse grid, coarse spacing
        quick, _ = run_grid(keys, spread(heights, 3), spread(overhangs, 2),
                            [5.0] if 5.0 in tilts else spread(tilts, 1), max_evals, 1.0, 0.0, 0.35)
        best_of = {}
        for c in quick:
            if c["phot"] not in best_of or c["npv_km"] < best_of[c["phot"]]:
                best_of[c["phot"]] = c["npv_km"]
        order = sorted(keys, key=lambda k: (k not in best_of, best_of.get(k, 0.0)))
        full_keys = order[:screen_keep]
        for k in order:
            screening.append(dict(phot=k, name=phot_lookup(k).name, npv_km=best_of.get(k),
                                  searched=k in full_keys))
        p0 = 0.35
    else:
        p0 = 0.0
    # 2) full search of the chosen luminaires
    cands, skipped = run_grid(full_keys, heights, overhangs, tilts, max_evals, 0.25, p0, 1.0)
    if progress:
        progress(1.0)
    cands.sort(key=lambda c: c["npv_km"])
    # keep the best of each arrangement / luminaire to give real alternatives
    seen, best = set(), []
    for c in cands:
        key = (c["arrangement"], c["phot"], c["H"])
        if key in seen:
            continue
        seen.add(key)
        best.append(c)
        if len(best) >= top:
            break
    found = {c["phot"] for c in cands}
    no_design = [k for k in full_keys if k not in found]
    return dict(candidates=best, n_evaluated=n_eval[0], n_feasible=len(cands),
                n_combinations=len(full_keys) * len(arrs) * len(heights) * len(overhangs) * len(tilts),
                rule=rule, tree_notes=sorted(set(tree_notes)), lines=lines,
                mode="full" if not screening else "screened", screening=screening,
                no_design=[dict(phot=k, name=phot_lookup(k).name) for k in no_design],
                incomplete=[dict(phot=k, name=phot_lookup(k).name) for k in skipped])


def _head_in_crown(rows, trees):
    for r in rows:
        yl = r["y"] + (1 if r["side"] >= 0 else -1) * r["overhang"]
        for tl in trees:
            base, top, rad = float(tl.get("crown_base", 3)), float(tl.get("height", 8)), float(tl.get("crown_radius", 2.5))
            if abs(yl - float(tl["y"])) < rad + 0.3 and base - 0.3 < r["height"] < top + 0.3:
                return True
    return False


def _mirror_symmetric(section):
    el = section["elements"]
    sig = lambda e: (e.get("kind"), round(float(e.get("width", 0)), 3), (e.get("cls") or "").upper(),
                     e.get("surface", "R3"), int(e.get("lanes", 0) or 0))
    return [sig(e) for e in el] == [sig(e) for e in reversed(el)]


def _rule_from_section(section):
    r = {}
    opts = section.get("options", {})
    for k in ("apply_Ul", "apply_REI", "p_upper", "apply_TI_P", "facial"):
        if k in opts:
            r[k] = bool(opts[k])
    for e in section["elements"]:
        if e.get("facial"):
            r["facial"] = True
    return r


def finalize(section, cand, phot_lookup, fM=0.8, rule=None):
    """Full evaluation (with display grids and TI) of a chosen candidate."""
    rows = cand["rows"]
    res = calc.evaluate(section, rows, cand["S"], phot_lookup, fM,
                        options=dict(display=True, ti=True))
    rule = rule or {}
    checks = []
    has_traffic = any(a["kind"] == "carriageway" and a["cls"] for a in res["areas"])
    for a in res["areas"]:
        if not a["cls"]:
            continue
        extra = [e for e in (section["elements"][a["index"]].get("extra") or [])]
        p_upper = rule.get("p_upper", True) and not (has_traffic and a["kind"] != "carriageway")
        crit = classes.check(a, a["cls"], extra,
                             dict(rule, facial=section["elements"][a["index"]].get("facial", False),
                                  p_upper=p_upper))
        a["checks"] = crit
        a["ok"] = all(c["ok"] for c in crit) if crit else True
        checks += crit
    res["ok"] = all(c["ok"] for c in checks) if checks else True
    return res
