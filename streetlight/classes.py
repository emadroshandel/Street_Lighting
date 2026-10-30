# Street Lighting — road lighting design to EN 13201, CIE 140 and IES RP-8.
# Copyright (C) 2026 Emad Roshandel — GPL-3.0-or-later (see LICENSE)
"""Lighting classes and conformity checks.

* EN 13201-2:2015  Tables 1-6 (M, C, P, HS, SC, EV) and Annex C (fTI for C / P)
* CEN/TR 13201-1:2014 parameter-weighting method for selecting M, C and P
  classes (a guideline; national annexes and client specifications may use
  other weightings, so the selection is offered as a starting point)
* ANSI/IESNA RP-8-00 (R2005) Tables 2, 3, 5-7 (illuminance, luminance,
  walkways).  RP-8-00 has been superseded (current edition: ANSI/IES RP-8-25)
  and the later editions changed the criteria; the RP-8 option reproduces the
  2000 criteria only.

Each check returns the value, the requirement and a plain-language reason,
so the report can say *why* a criterion passes or fails.
"""
from __future__ import annotations

# --------------------------------------------------------------------------
# EN 13201-2:2015
# --------------------------------------------------------------------------
M_CLASSES = {  # L, Uo, Ul, fTI max, REI min
    "M1": (2.00, 0.40, 0.70, 10, 0.35), "M2": (1.50, 0.40, 0.70, 10, 0.35),
    "M3": (1.00, 0.40, 0.60, 15, 0.30), "M4": (0.75, 0.40, 0.60, 15, 0.30),
    "M5": (0.50, 0.35, 0.40, 15, 0.30), "M6": (0.30, 0.35, 0.40, 20, 0.30),
}
C_CLASSES = {  # E avg, Uo, fTI max (Annex C)
    "C0": (50.0, 0.40, 15), "C1": (30.0, 0.40, 15), "C2": (20.0, 0.40, 15),
    "C3": (15.0, 0.40, 20), "C4": (10.0, 0.40, 20), "C5": (7.50, 0.40, 20),
}
P_CLASSES = {  # E avg, E min, Ev,min, Esc,min, fTI max (Annex C)
    "P1": (15.0, 3.00, 5.0, 5.0, 20), "P2": (10.0, 2.00, 3.0, 2.0, 25),
    "P3": (7.50, 1.50, 2.5, 1.5, 25), "P4": (5.00, 1.00, 1.5, 1.0, 30),
    "P5": (3.00, 0.60, 1.0, 0.6, 30), "P6": (2.00, 0.40, 0.6, 0.2, 35),
    "P7": (None, None, None, None, None),
}
HS_CLASSES = {"HS1": (5.00, 0.15), "HS2": (2.50, 0.15), "HS3": (1.00, 0.15), "HS4": (None, None)}
SC_CLASSES = {"SC1": 10.0, "SC2": 7.50, "SC3": 5.00, "SC4": 3.00, "SC5": 2.00, "SC6": 1.50,
              "SC7": 1.00, "SC8": 0.75, "SC9": 0.50}
EV_CLASSES = {"EV1": 50.0, "EV2": 30.0, "EV3": 10.0, "EV4": 7.50, "EV5": 5.00, "EV6": 0.50}

# --------------------------------------------------------------------------
# ANSI/IESNA RP-8-00
# --------------------------------------------------------------------------
RP8_LUMINANCE = {  # Lavg, Lavg/Lmin max, Lmax/Lmin max, Lv/Lavg max
    "Freeway A": (0.6, 3.5, 6.0, 0.3), "Freeway B": (0.4, 3.5, 6.0, 0.3),
    "Expressway High": (1.0, 3.0, 5.0, 0.3), "Expressway Medium": (0.8, 3.0, 5.0, 0.3),
    "Expressway Low": (0.6, 3.5, 6.0, 0.3),
    "Major High": (1.2, 3.0, 5.0, 0.3), "Major Medium": (0.9, 3.0, 5.0, 0.3),
    "Major Low": (0.6, 3.5, 6.0, 0.3),
    "Collector High": (0.8, 3.0, 5.0, 0.4), "Collector Medium": (0.6, 3.5, 6.0, 0.4),
    "Collector Low": (0.4, 4.0, 8.0, 0.4),
    "Local High": (0.6, 6.0, 10.0, 0.4), "Local Medium": (0.5, 6.0, 10.0, 0.4),
    "Local Low": (0.3, 6.0, 10.0, 0.4),
}
RP8_ILLUMINANCE = {  # (R1, R2&R3, R4) lux, Eavg/Emin max, Lv/Lavg max
    "Freeway A": ((6, 9, 8), 3.0, 0.3), "Freeway B": ((4, 6, 5), 3.0, 0.3),
    "Expressway High": ((10, 14, 13), 3.0, 0.3), "Expressway Medium": ((8, 12, 10), 3.0, 0.3),
    "Expressway Low": ((6, 9, 8), 3.0, 0.3),
    "Major High": ((12, 17, 15), 3.0, 0.3), "Major Medium": ((9, 13, 11), 3.0, 0.3),
    "Major Low": ((6, 9, 8), 3.0, 0.3),
    "Collector High": ((8, 12, 10), 4.0, 0.4), "Collector Medium": ((6, 9, 8), 4.0, 0.4),
    "Collector Low": ((4, 6, 5), 4.0, 0.4),
    "Local High": ((6, 9, 8), 6.0, 0.4), "Local Medium": ((5, 7, 6), 6.0, 0.4),
    "Local Low": ((3, 4, 4), 6.0, 0.4),
}
RP8_WALKWAY = {  # E_H avg, Ev,min, Eavg/Emin max
    "Walkway High mixed": (20.0, 10.0, 4.0), "Walkway High pedestrian": (10.0, 5.0, 4.0),
    "Walkway Medium": (5.0, 2.0, 4.0),
    "Walkway Low rural": (2.0, 0.6, 10.0), "Walkway Low residential": (3.0, 0.8, 6.0),
    "Walkway Low medium-density": (4.0, 1.0, 4.0),
}


def all_classes():
    return dict(
        EN13201=dict(M=list(M_CLASSES), C=list(C_CLASSES), P=list(P_CLASSES), HS=list(HS_CLASSES),
                     SC=list(SC_CLASSES), EV=list(EV_CLASSES)),
        RP8=dict(luminance=list(RP8_LUMINANCE), illuminance=list(RP8_ILLUMINANCE),
                 walkway=list(RP8_WALKWAY)),
        tables=dict(M=M_CLASSES, C=C_CLASSES, P=P_CLASSES, HS=HS_CLASSES, SC=SC_CLASSES,
                    EV=EV_CLASSES, RP8L=RP8_LUMINANCE, RP8E=RP8_ILLUMINANCE, RP8W=RP8_WALKWAY))


def _crit(name, sym, value, req, op, unit="", why_pass="", why_fail="", digits=2, advisory=False):
    if value is None or req is None:
        return None
    ok = value >= req - 1e-9 if op == ">=" else value <= req + 1e-9
    v = round(value, digits) if isinstance(value, float) else value
    d = dict(name=name, symbol=sym, value=v, req=req, op=op, unit=unit, ok=bool(ok or advisory),
             met=bool(ok), reason=(why_pass if ok else why_fail))
    if advisory:
        d["advisory"] = True
        if not ok:
            d["reason"] = why_fail + " (advisory: the area is lit by the carriageway luminaires)"
    return d


def kind_of(cls):
    c = (cls or "").upper().strip()
    if c.startswith("RP8:"):
        return "RP8"
    for k in ("HS", "SC", "EV", "M", "C", "P"):
        if c.startswith(k):
            return k
    return ""


def check(area, cls, extra=None, opts=None):
    """List of criteria for one area result (from calc.evaluate)."""
    opts = opts or {}
    cls = (cls or "").strip()
    k = kind_of(cls)
    c = []
    if k == "M" and cls.upper() in M_CLASSES and "L_avg" in area:
        L, U0, Ul, TI, REI = M_CLASSES[cls.upper()]
        c.append(_crit("Average road luminance", "L̄", area["L_avg"], L, ">=", "cd/m²",
                       "maintained luminance meets the class minimum",
                       "the road surface is too dark for drivers: increase flux, reduce spacing or height"))
        c.append(_crit("Overall uniformity", "Uo", area["U0_L"], U0, ">=", "",
                       "darkest point is bright enough relative to the average",
                       "dark patches: reduce spacing, raise the mounting height or widen the optic"))
        if opts.get("apply_Ul", True):
            c.append(_crit("Longitudinal uniformity", "Ul", area["Ul"], Ul, ">=", "",
                           "bright/dark pattern along the lane is acceptable",
                           "strong bright-dark banding along the lane: reduce spacing"))
        if area.get("TI") is not None:
            c.append(_crit("Threshold increment", "fTI", area["TI"], TI, "<=", "%",
                           "disability glare is limited", "too much glare: use a sharper cut-off, "
                           "less tilt or a higher mounting", digits=1))
        rei = (area.get("REI") or {}).get("value")
        if rei is not None and opts.get("apply_REI", True):
            c.append(_crit("Edge illuminance ratio", "REI", rei, REI, ">=", "",
                           "the road surroundings are lit", "the kerb zone is dark: add house-side light "
                           "or move the poles"))
    elif k == "C" and cls.upper() in C_CLASSES:
        E, U0, TI = C_CLASSES[cls.upper()]
        c.append(_crit("Average illuminance", "Ē", area["E_avg"], E, ">=", "lx",
                       "illuminance meets the class", "illuminance too low"))
        c.append(_crit("Overall uniformity", "Uo", area["U0_E"], U0, ">=", "",
                       "even illumination", "uneven illumination: reduce spacing"))
        if area.get("TI") is not None:
            c.append(_crit("Threshold increment (Annex C)", "fTI", area["TI"], TI, "<=", "%",
                           "glare limited", "glare too high", digits=1))
    elif k == "P" and cls.upper() in P_CLASSES and P_CLASSES[cls.upper()][0] is not None:
        E, Emin, Ev, Esc, TI = P_CLASSES[cls.upper()]
        c.append(_crit("Average illuminance", "Ē", area["E_avg"], E, ">=", "lx",
                       "illuminance meets the class", "too dark for pedestrians"))
        c.append(_crit("Average illuminance — upper limit (1.5 × Ē)", "Ē", area["E_avg"],
                       round(1.5 * E, 3), "<=", "lx", "not over-lit (Table 3 note a)",
                       "over-lit: the average must not exceed 1.5 × the class value — dim or "
                       "choose a lower lumen package", advisory=not opts.get("p_upper", True)))
        c.append(_crit("Minimum illuminance", "Emin", area["E_min"], Emin, ">=", "lx",
                       "no dark spots", "dark spots between poles"))
        if opts.get("facial"):
            c.append(_crit("Min. vertical illuminance (1.5 m)", "Ev,min", area["Ev_min"], Ev, ">=", "lx",
                           "faces are visible", "faces poorly lit"))
            c.append(_crit("Min. semi-cylindrical illuminance (1.5 m)", "Esc,min", area["Esc_min"], Esc,
                           ">=", "lx", "faces are recognisable", "facial recognition poor"))
        if area.get("TI") is not None and opts.get("apply_TI_P", False):
            c.append(_crit("Threshold increment (Annex C)", "fTI", area["TI"], TI, "<=", "%",
                           "glare limited", "glare too high", digits=1))
    elif k == "HS" and HS_CLASSES.get(cls.upper(), (None,))[0] is not None:
        E, U0 = HS_CLASSES[cls.upper()]
        c.append(_crit("Average hemispherical illuminance", "Ēhs", area["Ehs_avg"], E, ">=", "lx",
                       "meets the class", "too dark"))
        c.append(_crit("Uniformity of Ehs", "Uo", area["U0_hs"], U0, ">=", "", "even", "uneven"))
    elif k == "RP8":
        name = cls[4:].strip()
        if name in RP8_LUMINANCE and "L_avg" in area:
            L, r1, r2, rv = RP8_LUMINANCE[name]
            Lmin = min(o["L_min"] for o in area["observers"])
            Lmax = max(o["L_max"] for o in area["observers"])
            c.append(_crit("Average luminance", "Lavg", area["L_avg"], L, ">=", "cd/m²",
                           "meets RP-8 Table 3", "too dark"))
            c.append(_crit("Lavg / Lmin", "Lavg/Lmin", area["L_avg"] / max(Lmin, 1e-9), r1, "<=", "",
                           "uniform", "non-uniform"))
            c.append(_crit("Lmax / Lmin", "Lmax/Lmin", Lmax / max(Lmin, 1e-9), r2, "<=", "",
                           "uniform", "non-uniform"))
            if area.get("Lv") is not None and area["L_avg"] > 0:
                c.append(_crit("Veiling luminance ratio", "Lv/Lavg", area["Lv"] / (area["L_avg"] / area.get("fM", 1.0)),
                               rv, "<=", "", "glare limited", "glare too high"))
        elif name in RP8_WALKWAY:
            E, Ev, r = RP8_WALKWAY[name]
            c.append(_crit("Average horizontal illuminance", "EH", area["E_avg"], E, ">=", "lx",
                           "meets RP-8", "too dark"))
            c.append(_crit("Min. vertical illuminance (1.5 m)", "Ev,min", area["Ev_min"], Ev, ">=", "lx",
                           "meets RP-8", "too dark"))
            c.append(_crit("Eavg / Emin", "Eavg/Emin", area["E_avg"] / max(area["E_min"], 1e-9), r, "<=",
                           "", "uniform", "non-uniform"))
        elif name in RP8_ILLUMINANCE:
            (e1, e23, e4), r, rv = RP8_ILLUMINANCE[name]
            surf = area.get("surface", "R3")
            E = e1 if surf == "R1" else e4 if surf == "R4" else e23
            c.append(_crit("Average illuminance", "Eavg", area["E_avg"], float(E), ">=", "lx",
                           "meets RP-8 Table 2", "too dark"))
            c.append(_crit("Eavg / Emin", "Eavg/Emin", area["E_avg"] / max(area["E_min"], 1e-9), r, "<=",
                           "", "uniform", "non-uniform"))
    # additional classes (SC / EV) for pedestrian areas
    for x in (extra or []):
        x = x.upper()
        if x in SC_CLASSES:
            c.append(_crit("Min. semi-cylindrical illuminance", "Esc,min", area["Esc_min"], SC_CLASSES[x],
                           ">=", "lx", "faces recognisable (%s)" % x, "below %s" % x))
        if x in EV_CLASSES:
            c.append(_crit("Min. vertical illuminance", "Ev,min", area["Ev_min"], EV_CLASSES[x],
                           ">=", "lx", "vertical surfaces visible (%s)" % x, "below %s" % x))
    return [x for x in c if x]


def target_level(cls, surface="R3"):
    """(quantity, value) that sets the required flux for a class."""
    k = kind_of(cls)
    c = cls.upper()
    if k == "M":
        return "L_avg", M_CLASSES[c][0]
    if k == "C":
        return "E_avg", C_CLASSES[c][0]
    if k == "P" and P_CLASSES.get(c, (None,))[0] is not None:
        return "E_avg", P_CLASSES[c][0]
    if k == "HS" and HS_CLASSES.get(c, (None,))[0] is not None:
        return "Ehs_avg", HS_CLASSES[c][0]
    if k == "RP8":
        n = cls[4:].strip()
        if n in RP8_LUMINANCE:
            return "L_avg", RP8_LUMINANCE[n][0]
        if n in RP8_WALKWAY:
            return "E_avg", RP8_WALKWAY[n][0]
        if n in RP8_ILLUMINANCE:
            e = RP8_ILLUMINANCE[n][0]
            return "E_avg", float(e[0] if surface == "R1" else e[2] if surface == "R4" else e[1])
    return None, None


def upper_limit(cls):
    """Maximum flux ratio allowed by the class (P classes: 1.5 x Ē)."""
    if kind_of(cls) == "P":
        return 1.5
    return None


# --------------------------------------------------------------------------
# CEN/TR 13201-1:2014 class selection
# --------------------------------------------------------------------------
SELECTION = {
    "M": [
        ("speed", "Design speed or speed limit", [
            ("very_high", "Very high (v ≥ 100 km/h)", 2), ("high", "High (70 < v < 100 km/h)", 1),
            ("moderate", "Moderate (40 < v ≤ 70 km/h)", -1), ("low", "Low (v ≤ 40 km/h)", -2)]),
        ("volume", "Traffic volume", [
            ("high", "High", 1), ("moderate", "Moderate", 0), ("low", "Low", -1)]),
        ("composition", "Traffic composition", [
            ("mixed_high_nonmotor", "Mixed with a high share of non-motorised users", 2),
            ("mixed", "Mixed", 1), ("motor_only", "Motorised only", 0)]),
        ("separation", "Separation of carriageways", [("no", "No", 1), ("yes", "Yes", 0)]),
        ("junctions", "Junction density", [("high", "High", 1), ("moderate", "Moderate", 0)]),
        ("parked", "Parked vehicles", [("present", "Present", 1), ("absent", "Not present", 0)]),
        ("ambient", "Ambient luminosity", [("high", "High (shops, floodlit areas)", 1),
                                           ("moderate", "Moderate", 0), ("low", "Low (rural)", -1)]),
        ("navigation", "Navigational task", [("very_difficult", "Very difficult", 2),
                                             ("difficult", "Difficult", 1), ("easy", "Easy", 0)]),
    ],
    "C": [
        ("speed", "Design speed or speed limit", [
            ("very_high", "Very high (v ≥ 100 km/h)", 3), ("high", "High (70 < v < 100 km/h)", 2),
            ("moderate", "Moderate (40 < v ≤ 70 km/h)", 0), ("low", "Low (v ≤ 40 km/h)", -1)]),
        ("volume", "Traffic volume", [("high", "High", 1), ("moderate", "Moderate", 0), ("low", "Low", -1)]),
        ("composition", "Traffic composition", [
            ("mixed_high_nonmotor", "Mixed with a high share of non-motorised users", 2),
            ("mixed", "Mixed", 1), ("motor_only", "Motorised only", 0)]),
        ("separation", "Separation of carriageways", [("no", "No", 1), ("yes", "Yes", 0)]),
        ("parked", "Parked vehicles", [("present", "Present", 1), ("absent", "Not present", 0)]),
        ("ambient", "Ambient luminosity", [("high", "High", 1), ("moderate", "Moderate", 0), ("low", "Low", -1)]),
        ("navigation", "Navigational task", [("very_difficult", "Very difficult", 2),
                                             ("difficult", "Difficult", 1), ("easy", "Easy", 0)]),
    ],
    "P": [
        ("speed", "Travel speed", [("low", "Low (v ≤ 40 km/h)", 1), ("very_low", "Very low (walking)", 0)]),
        ("use", "Intensity of use", [("busy", "Busy", 1), ("normal", "Normal", 0), ("quiet", "Quiet", -1)]),
        ("composition", "Traffic composition", [
            ("ped_cyc_motor", "Pedestrians, cyclists and motor traffic", 2),
            ("ped_motor", "Pedestrians and motor traffic", 1), ("ped_cyc", "Pedestrians and cyclists only", 1),
            ("ped_only", "Pedestrians only", 0), ("cyc_only", "Cyclists only", 0)]),
        ("parked", "Parked vehicles", [("present", "Present", 1), ("absent", "Not present", 0)]),
        ("ambient", "Ambient luminosity", [("high", "High", 1), ("moderate", "Moderate", 0), ("low", "Low", -1)]),
        ("facial", "Facial recognition", [("necessary", "Necessary (adds Ev / Esc requirements)", 0),
                                          ("not_necessary", "Not necessary", 0)]),
    ],
}


def select_class(series, answers):
    """Return the class from the weighting values: class number = 6 - sum."""
    series = series.upper()
    rows = SELECTION[series]
    total = 0
    detail = []
    for key, label, opts in rows:
        val = answers.get(key, opts[0][0])
        w = next((o[2] for o in opts if o[0] == val), 0)
        total += w
        detail.append(dict(key=key, label=label, choice=val, weight=w))
    n = 6 - total
    lo = 0 if series == "C" else 1
    hi = 5 if series == "C" else 6
    n = min(max(n, lo), hi)
    cls = "%s%d" % (series, n)
    return dict(cls=cls, sum=total, detail=detail,
                facial=answers.get("facial") == "necessary" if series == "P" else False,
                note="CEN/TR 13201-1:2014 weighting method (class = 6 − ΣVW). "
                     "Confirm against the national annex or the client's specification.")


ROAD_TYPES = [
    # key, label, typical class (EN), RP-8 class, default speed
    ("motorway", "Motorway / freeway", "M1", "RP8:Freeway A", 110),
    ("expressway", "Expressway / dual carriageway", "M2", "RP8:Expressway Medium", 90),
    ("arterial", "Urban arterial / major road", "M3", "RP8:Major Medium", 60),
    ("collector", "Collector / distributor road", "M4", "RP8:Collector Medium", 50),
    ("local", "Local street", "M5", "RP8:Local Medium", 40),
    ("residential", "Residential street", "P3", "RP8:Local Low", 30),
    ("rural", "Rural road", "M5", "RP8:Collector Low", 80),
    ("pedestrian", "Pedestrian street / plaza", "P2", "RP8:Walkway High pedestrian", 5),
    ("cycleway", "Footpath / cycleway", "P4", "RP8:Walkway Medium", 15),
    ("alley", "Lane / alley", "P5", "RP8:Walkway Low residential", 20),
    ("intersection", "Conflict area / intersection", "C2", "RP8:Major Medium", 50),
]
