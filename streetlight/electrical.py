# Street Lighting — road lighting design to EN 13201, CIE 140 and IES RP-8.
# Copyright (C) 2026 Emad Roshandel — GPL-3.0-or-later (see LICENSE)
"""Supply design: feeder pillars, circuits, phase allocation, cable sizing.

* Current-carrying capacity: IEC 60364-5-52:2009 Tables B.52.2-B.52.5
  (methods D1 = cable in buried duct, D2 = cable direct in ground) with the
  ground-temperature (B.52.15), soil-resistivity (B.52.16) and grouping
  (B.52.18 / B.52.19) correction factors.
* Voltage drop: IEC 60364-5-52 Annex G, computed exactly for the
  distributed load: phasor currents per phase and in the neutral, segment by
  segment (rho1 = 1.25 rho20, lambda = 0.08 mOhm/m).
* Protection: Ib <= In <= Iz (IEC 60364-4-43); automatic disconnection
  (IEC 60364-4-41): TN — Zs <= Cmin U0 / Ia with Ia for 0.4 s (final circuits
  <= 32 A for fixed equipment) or 5 s; TT — RA x I_delta_n <= 50 V.
* gG fuses: IEC 60269-1 Table 3 / IEC 60269-2-1 Table III gates (see GG_GATES).
* Short-circuit withstand: adiabatic S >= I sqrt(t) / k.
* Conductor resistances: IEC 60228 class 2 at 20 deg C.

The search tries 1..n feeder pillars, every pole as the pillar position and
every standard cable size, and keeps the cheapest arrangement that passes.
"""
from __future__ import annotations

import cmath
import math

import numpy as np

SIZES = {"Cu": [6, 10, 16, 25, 35, 50, 70, 95, 120, 150, 185, 240],
         "Al": [16, 25, 35, 50, 70, 95, 120, 150, 185, 240]}

# IEC 60228 class 2, ohm/km at 20 C
R20 = {"Cu": {1.5: 12.1, 2.5: 7.41, 4: 4.61, 6: 3.08, 10: 1.83, 16: 1.15, 25: 0.727, 35: 0.524,
              50: 0.387, 70: 0.268, 95: 0.193, 120: 0.153, 150: 0.124, 185: 0.0991, 240: 0.0754,
              300: 0.0601},
       "Al": {16: 1.91, 25: 1.20, 35: 0.868, 50: 0.641, 70: 0.443, 95: 0.320, 120: 0.253,
              150: 0.206, 185: 0.164, 240: 0.125, 300: 0.100}}

# IEC 60364-5-52 three loaded conductors, methods D1 / D2 (A)
IZ = {
    ("Cu", "PVC", "D1"): {6: 38, 10: 50, 16: 64, 25: 82, 35: 98, 50: 116, 70: 143, 95: 169, 120: 192,
                          150: 217, 185: 243, 240: 280, 300: 316},
    ("Cu", "PVC", "D2"): {6: 41, 10: 54, 16: 70, 25: 92, 35: 110, 50: 130, 70: 162, 95: 193, 120: 220,
                          150: 246, 185: 278, 240: 320, 300: 359},
    ("Cu", "XLPE", "D1"): {6: 44, 10: 58, 16: 75, 25: 96, 35: 115, 50: 135, 70: 167, 95: 197, 120: 223,
                           150: 251, 185: 281, 240: 324, 300: 365},
    ("Cu", "XLPE", "D2"): {6: 49, 10: 65, 16: 84, 25: 107, 35: 129, 50: 153, 70: 188, 95: 226, 120: 257,
                           150: 287, 185: 324, 240: 375, 300: 419},
    ("Al", "PVC", "D1"): {16: 50, 25: 64, 35: 77, 50: 91, 70: 112, 95: 132, 120: 150, 150: 169, 185: 190,
                          240: 218, 300: 247},
    ("Al", "PVC", "D2"): {16: 53, 25: 69, 35: 83, 50: 99, 70: 122, 95: 148, 120: 169, 150: 189, 185: 214,
                          240: 250, 300: 282},
    ("Al", "XLPE", "D1"): {16: 59, 25: 75, 35: 90, 50: 106, 70: 130, 95: 154, 120: 174, 150: 197, 185: 220,
                           240: 253, 300: 286},
    ("Al", "XLPE", "D2"): {16: 64, 25: 82, 35: 98, 50: 117, 70: 144, 95: 172, 120: 197, 150: 220, 185: 250,
                           240: 290, 300: 326},
}

K_TEMP = {"PVC": {10: 1.10, 15: 1.05, 20: 1.00, 25: 0.95, 30: 0.89, 35: 0.84, 40: 0.77, 45: 0.71, 50: 0.63},
          "XLPE": {10: 1.07, 15: 1.04, 20: 1.00, 25: 0.96, 30: 0.93, 35: 0.89, 40: 0.85, 45: 0.80, 50: 0.76}}
K_SOIL = {"D1": {0.5: 1.28, 0.7: 1.20, 1.0: 1.18, 1.5: 1.10, 2.0: 1.05, 2.5: 1.00, 3.0: 0.96},
          "D2": {0.5: 1.88, 0.7: 1.62, 1.0: 1.50, 1.5: 1.28, 2.0: 1.12, 2.5: 1.00, 3.0: 0.90}}
K_GROUP_D2 = {1: 1.0, 2: 0.75, 3: 0.65, 4: 0.60, 5: 0.55, 6: 0.50}       # touching
K_GROUP_D1 = {1: 1.0, 2: 0.85, 3: 0.75, 4: 0.70, 5: 0.65, 6: 0.60}       # ducts touching
K_ADIABATIC = {("Cu", "PVC"): 115, ("Cu", "XLPE"): 143, ("Al", "PVC"): 76, ("Al", "XLPE"): 94}
RHO1 = {"Cu": 0.0225, "Al": 0.036}                                        # ohm mm2/m (Annex G)
RATINGS = [6, 10, 13, 16, 20, 25, 32, 40, 50, 63, 80, 100, 125, 160]
# gG fuse-link gates (A): In -> (Imax(5 s), Imax(0.1 s)).
# IEC 60269-1:2006+A2:2014 Table 3 (16 A and above) and IEC 60269-2-1:2002 Table III (below 16 A).
# Imax(5 s) is the current that certainly operates the fuse within 5 s.  The standards give no 0.4 s
# gate, so for 0.4 s Imax(0.1 s) is used: it is guaranteed but conservative (typical fuse curves
# operate at roughly half of it); a value from the fuse maker's curve can be entered instead.
GG_GATES = {2: (9.2, 23.0), 4: (18.5, 47.0), 6: (28.0, 72.0), 8: (35.2, 92.0), 10: (46.5, 110.0),
            12: (55.2, 140.4), 16: (65.0, 150.0), 20: (85.0, 200.0), 25: (110.0, 260.0), 32: (150.0, 350.0),
            35: (175.0, 445.0), 40: (190.0, 450.0), 50: (250.0, 610.0), 63: (320.0, 820.0),
            80: (425.0, 1100.0), 100: (580.0, 1450.0), 125: (715.0, 1910.0), 160: (950.0, 2590.0)}


def _validate(cfg):
    """Plain-language errors for supply data that cannot be designed with."""
    def need(cond, msg):
        if not cond:
            raise ValueError(msg)
    for k in ("U0", "pf", "Ze", "du_max", "Ik_pillar", "t_fault", "pole_cable_mm2", "max_pillars"):
        try:
            cfg[k] = float(cfg[k]) if k != "max_pillars" else int(cfg[k])
        except (TypeError, ValueError):
            raise ValueError("Electrical input '%s' must be a number." % k) from None
    need(50 <= cfg["U0"] <= 1000, "Phase voltage U0 must lie between 50 and 1000 V.")
    need(0.3 <= cfg["pf"] <= 1.0, "Power factor must lie between 0.3 and 1.0.")
    need(cfg["Ze"] >= 0, "Supply impedance Ze cannot be negative.")
    need(cfg["du_max"] > 0, "The allowed voltage drop must be greater than zero.")
    need(cfg["Ik_pillar"] > 0 and cfg["t_fault"] > 0, "Fault current and fault duration must be greater than zero.")
    need(cfg["pole_cable_mm2"] > 0, "The column cable size must be greater than zero.")
    need(1 <= cfg["max_pillars"] <= 50, "The number of feeder pillars to try must lie between 1 and 50.")
    need((cfg["material"], cfg["insulation"], cfg["method"]) in IZ,
         "Unknown cable: %s / %s / method %s." % (cfg["material"], cfg["insulation"], cfg["method"]))
    if cfg.get("gg_k04") not in (None, ""):
        cfg["gg_k04"] = float(cfg["gg_k04"])
        need(2.0 <= cfg["gg_k04"] <= 30.0, "gG fuse Ia/In at 0.4 s must lie between 2 and 30 (read it from the fuse curve).")
    else:
        cfg["gg_k04"] = None
    if str(cfg["system"]).upper().startswith("TT"):
        need(float(cfg["RA"]) >= 0 and float(cfg["Idn"]) > 0, "TT: RA must be ≥ 0 and IΔn greater than zero.")


def installation_notes(poles):
    """Requirements of IEC 60364-7-714:2011 (external lighting installations) to observe on site."""
    n = [
        "Every circuit can be isolated individually from each live supply conductor (714.536.2.1.1).",
        "Column doors less than 2.5 m above ground are locked with a key or tool, and live parts behind them are "
        "protected to IPXXB / IP2X when the door is open (714.41 Annex A).",
        "All electrical equipment has at least IP33 by construction or installation (714.512.2.105); "
        "minimum external influences AD3 (sprays) and AE2 (small objects).",
        "Lit kiosks, bus shelters, advertising panels and town plans get additional protection by a 30 mA RCD "
        "(714.411.3.3).",
    ]
    low = [p for p in poles if float(p.get("H", 10.0)) < 2.8]
    if low:
        n.append("%d luminaire(s) below 2.8 m: the light source must be reachable only after removing a barrier "
                 "or enclosure with a tool (714.41 Annex A); in Ireland a 30 mA RCD is also required." % len(low))
    n.append("IEC 60364-7-714 does not apply to public street lighting that is part of the public power grid; "
             "the network operator's rules govern there (714.1).")
    return n


def _interp_table(tab, x):
    ks = sorted(tab)
    if x <= ks[0]:
        return tab[ks[0]]
    if x >= ks[-1]:
        return tab[ks[-1]]
    for a, b in zip(ks, ks[1:]):
        if a <= x <= b:
            return tab[a] + (tab[b] - tab[a]) * (x - a) / (b - a)


def ampacity(size, mat="Cu", ins="XLPE", method="D2", t_ground=20.0, rho_soil=2.5, n_group=1):
    base = IZ[(mat, ins, method)][size]
    kt = _interp_table(K_TEMP[ins], t_ground)
    ks = _interp_table(K_SOIL[method], rho_soil)
    kg = (K_GROUP_D2 if method == "D2" else K_GROUP_D1).get(min(max(n_group, 1), 6))
    return base * kt * ks * kg, dict(base=base, k_temp=kt, k_soil=ks, k_group=kg)


def trip_current(device, In, t, gg_k04=None):
    """Ia that operates the device within t seconds.

    MCB B / C / D: upper limit of the instantaneous release, 5 / 10 / 20 In (IEC 60898-1).
    gG fuse: IEC 60269 gates — Imax(5 s) for 5 s; for 0.4 s Imax(0.1 s), or gg_k04 x In when the
    ratio Ia/In at 0.4 s is taken from the fuse maker's time-current curve.
    """
    d = device.upper()
    if d in ("B", "MCB-B"):
        return 5.0 * In
    if d in ("C", "MCB-C"):
        return 10.0 * In
    if d in ("D", "MCB-D"):
        return 20.0 * In
    if d == "GG":
        if t <= 0.4 and gg_k04:
            return float(gg_k04) * In
        # a rating between table values (e.g. 13 A) takes the next larger rating: conservative
        k = next((r for r in sorted(GG_GATES) if r >= In), max(GG_GATES))
        imax5, imax01 = GG_GATES[k]
        return imax01 if t <= 0.4 else imax5
    return 5.0 * In


DEFAULT = dict(
    system="TN-S", U0=230.0, Un=400.0, pf=0.95, material="Cu", insulation="XLPE", method="D2",
    t_ground=25.0, rho_soil=2.5, n_group=1, du_max=3.0, device="C", Ze=0.35, RA=30.0, Idn=0.3,
    Ik_pillar=6000.0, t_fault=0.1, pole_cable_mm2=2.5, pole_cable_extra=2.0, crossing_extra=0.0,
    max_drivers_B16=20, inrush_note=True,
    cable_cost=dict(Cu=0.30, Al=0.12), cable_cost_fixed=2.5, pillar_cost=1800.0,
    trench_cost=15.0, max_pillars=12, allow_split_phase=True, three_phase=True,
    feeders_per_pillar=2,
)


def _segment_lengths(poles, side_extra=0.0):
    """Cable lengths between consecutive poles of a run (route chainage + world distance)."""
    L = []
    for a, b in zip(poles, poles[1:]):
        d = math.hypot(b["x"] - a["x"], b["yw"] - a["yw"])
        L.append(max(d, abs(b["s"] - a["s"])) * 1.03 + 1.0)      # 3 % snaking + 1 m at each pole
    return L


def feeder_calc(loads, seg_len, size, cfg, phases=None):
    """Exact voltage drop / currents of one radial three-phase feeder.

    loads: list of W per node (node 1..n downstream of the pillar)
    seg_len: lengths (m) pillar->node1, node1->node2, ...
    Returns dict with Ib, du_max (%), and per-node du (%).
    """
    mat = cfg["material"]
    U0, pf = cfg["U0"], cfg["pf"]
    n = len(loads)
    if phases is None:
        phases = [i % 3 for i in range(n)] if cfg.get("three_phase", True) else [0] * n
    ang = [0.0, -2 * math.pi / 3, 2 * math.pi / 3]
    phi = math.acos(min(max(pf, 0.05), 1.0))
    # current phasor of each load, referred to its phase voltage
    Iload = [loads[i] / (U0 * pf) * cmath.exp(1j * (ang[phases[i]] - phi)) for i in range(n)]
    R = RHO1[mat] / size                                      # ohm/m
    X = 0.08e-3                                               # ohm/m
    Z = [complex(R * L, X * L) for L in seg_len]
    # downstream sums per segment
    Iph = np.zeros((n, 3), complex)
    for k in range(n):
        for i in range(k, n):
            Iph[k, phases[i]] += Iload[i]
    In_seg = Iph.sum(1)                                       # neutral current (phasor sum)
    du_node = []
    Vdrop = np.zeros(3, complex)
    for k in range(n):
        # line and neutral conductors of the same section
        Vdrop = Vdrop + Z[k] * Iph[k] + Z[k] * In_seg[k]        # line + neutral return
        p = phases[k]
        dv = Vdrop[p]
        # drop projected on the phase voltage, plus the pole cable
        drop = (dv * cmath.exp(-1j * ang[p])).real
        lp = cfg["pole_cable_extra"] + loads_height(k, cfg)
        drop += 2 * RHO1["Cu"] / cfg["pole_cable_mm2"] * lp * loads[k] / U0
        du_node.append(100.0 * drop / U0)
    Ib = float(np.abs(Iph[0]).max()) if n else 0.0
    return dict(Ib=Ib, du=du_node, du_max=max(du_node) if du_node else 0.0,
                I_neutral=float(abs(In_seg[0])) if n else 0.0, phases=phases)


def loads_height(k, cfg):
    return cfg.get("_heights", [10.0] * (k + 1))[k] if k < len(cfg.get("_heights", [])) else 10.0


def _check_feeder(run, seg, size, cfg):
    """Size checks of one feeder for a given cable size; returns (ok, details)."""
    loads = [p["W"] for p in run]
    cfg = dict(cfg, _heights=[p["H"] for p in run])
    fc = feeder_calc(loads, seg, size, cfg)
    Ib = fc["Ib"]
    Iz, kf = ampacity(size, cfg["material"], cfg["insulation"], cfg["method"], cfg["t_ground"],
                      cfg["rho_soil"], cfg["n_group"])
    In = next((r for r in RATINGS if r >= Ib), None)
    msgs = []
    ok = True
    if In is None or In > Iz:
        ok = False
        msgs.append("Ib %.1f A needs a device larger than the cable capacity Iz %.0f A" % (Ib, Iz))
        In = In or RATINGS[-1]
    if fc["du_max"] > cfg["du_max"]:
        ok = False
        msgs.append("voltage drop %.2f %% > %.1f %%" % (fc["du_max"], cfg["du_max"]))
    # fault loop to the farthest luminaire (line + PE of the same size, rho1)
    Lsum = sum(seg)
    r = RHO1[cfg["material"]] / size
    lp = cfg["pole_cable_extra"] + run[-1]["H"]
    Zs = cfg["Ze"] + 2 * r * Lsum + 2 * RHO1["Cu"] / cfg["pole_cable_mm2"] * lp
    t = 0.4 if In <= 32 else 5.0
    dev = cfg["device"]
    if cfg["system"].upper().startswith("TT"):
        t = 0.2 if In <= 32 else 1.0
        ok_tt = cfg["RA"] * cfg["Idn"] <= 50.0
        if not ok_tt:
            ok = False
            msgs.append("TT: RA x IΔn = %.0f V > 50 V — lower RA or use a 30/100 mA RCD"
                        % (cfg["RA"] * cfg["Idn"]))
        Ia = cfg["Idn"]
        zs_ok = True
        Zs_max = 50.0 / cfg["Idn"]
    else:
        Ia = trip_current(dev, In, t, cfg.get("gg_k04"))
        Zs_max = 0.95 * cfg["U0"] / Ia
        zs_ok = Zs <= Zs_max
        if not zs_ok:
            ok = False
            msgs.append("fault loop Zs %.2f Ω > %.2f Ω (device %s%d, %.1f s)" % (Zs, Zs_max, dev, In, t))
    # short-circuit withstand at the pillar
    k = K_ADIABATIC[(cfg["material"], cfg["insulation"])]
    Smin = cfg["Ik_pillar"] * math.sqrt(cfg["t_fault"]) / k
    if size < Smin:
        ok = False
        msgs.append("short-circuit withstand needs ≥ %.1f mm²" % Smin)
    # inrush of LED drivers
    n_phase = max(fc["phases"].count(p) for p in range(3)) if fc["phases"] else 0
    n_allowed = cfg["max_drivers_B16"] * In / 16.0 * (1.7 if dev.upper() in ("C", "MCB-C") else 1.0)
    inrush_ok = n_phase <= n_allowed
    if not inrush_ok:
        msgs.append("inrush: %d drivers on one phase, about %.0f allowed for %s%d — consider a "
                    "C/D curve, an inrush limiter or a contactor" % (n_phase, n_allowed, dev, In))
    return ok, dict(size=size, Ib=Ib, In=In, Iz=Iz, k=kf, du_max=fc["du_max"], du=fc["du"],
                    Zs=Zs, Zs_max=Zs_max, Ia=Ia, t=t, I_neutral=fc["I_neutral"], phases=fc["phases"],
                    length=Lsum, inrush_ok=inrush_ok, n_per_phase=n_phase, msgs=msgs, ok=ok)


def _best_size(run, seg, cfg):
    for size in SIZES[cfg["material"]]:
        if size not in IZ[(cfg["material"], cfg["insulation"], cfg["method"])]:
            continue
        ok, d = _check_feeder(run, seg, size, cfg)
        if ok:
            return d
    d = _check_feeder(run, seg, SIZES[cfg["material"]][-1], cfg)[1]
    return d


def _cable_cost(size, length, cfg):
    return length * (cfg["cable_cost_fixed"] + cfg["cable_cost"][cfg["material"]] * size)


def design(poles, lum_power, config=None):
    """Feeder pillars and circuits for the poles of a layout.

    poles: from road.layout (with x, yw, s, y, H) — each pole carries one
    luminaire per entry; luminaires on the same pole share the drop cable.
    lum_power: dict phot_key -> W (system power at full output).
    """
    cfg = dict(DEFAULT)
    cfg.update({k: v for k, v in (config or {}).items() if v is not None})
    _validate(cfg)
    # group luminaires by pole position (twin heads share one pole)
    by_pole = {}
    for p in poles:
        key = (round(p["s"], 2), round(p["y"], 2))
        q = by_pole.setdefault(key, dict(s=p["s"], y=p["y"], x=p["x"], yw=p["yw"], H=p["H"], W=0.0,
                                         ids=[], side=p["side"]))
        q["W"] += float(lum_power.get(p["phot"], 100.0))
        q["ids"].append(p["id"])
    pts = sorted(by_pole.values(), key=lambda q: q["s"])
    # runs: poles grouped by their line across the road
    ys = sorted({round(q["y"], 1) for q in pts})
    runs = []
    for yv in ys:
        r = [q for q in pts if abs(q["y"] - yv) < 0.15]
        if r:
            runs.append(r)
    best = None
    for n_p in range(1, cfg["max_pillars"] + 1):
        bounds = np.linspace(min(q["s"] for q in pts) - 1e-6, max(q["s"] for q in pts) + 1e-6, n_p + 1)
        pillars, feeders, cost, ok_all = [], [], 0.0, True
        for k in range(n_p):
            a, b = bounds[k], bounds[k + 1]
            # pillar candidate positions: poles of the first run inside the zone
            zone_runs = [[q for q in r if a <= q["s"] <= b] for r in runs]
            zone_runs = [z for z in zone_runs if z]
            if not zone_runs:
                continue
            cands = zone_runs[0]
            best_local = None
            step = max(1, len(cands) // 12)
            for ci in range(0, len(cands), step):
                piv = cands[ci]
                fl, c_local, ok_local = [], cfg["pillar_cost"], True
                for zi, z in enumerate(zone_runs):
                    # crossing to other runs
                    cross = abs(z[0]["y"] - piv["y"]) * 1.2 + 2.0 if zi > 0 else 0.0
                    j = min(range(len(z)), key=lambda i: abs(z[i]["s"] - piv["s"]))
                    for direction, part in (("down", z[:j + 1][::-1]), ("up", z[j + 1:])):
                        if not part:
                            continue
                        first = math.hypot(part[0]["x"] - piv["x"], part[0]["yw"] - piv["yw"]) * 1.03 + 2.0 + cross
                        seg = [first] + _segment_lengths(part)
                        d = _best_size(part, seg, cfg)
                        c_local += _cable_cost(d["size"], d["length"], cfg) + cfg["trench_cost"] * d["length"]
                        ok_local &= d["ok"]
                        fl.append(dict(d, run=zi, direction=direction,
                                       poles=[dict(s=q["s"], y=q["y"], x=q["x"], yw=q["yw"], W=q["W"],
                                                   ids=q["ids"]) for q in part]))
                if best_local is None or (ok_local, -c_local) > (best_local[2], -best_local[1]):
                    best_local = (piv, c_local, ok_local, fl)
            piv, c_local, ok_local, fl = best_local
            ok_all &= ok_local
            cost += c_local
            pid = "FP%d" % (len(pillars) + 1)
            for f_i, f in enumerate(fl):
                f["id"] = "%s/F%d" % (pid, f_i + 1)
                f["pillar"] = pid
            pillars.append(dict(id=pid, s=piv["s"], y=piv["y"], x=piv["x"], yw=piv["yw"],
                                n_feeders=len(fl), load_W=sum(q["W"] for f in fl for q in f["poles"]),
                                ok=ok_local))
            feeders += fl
        sol = dict(n_pillars=len(pillars), pillars=pillars, feeders=feeders, cost=cost, ok=ok_all)
        if ok_all:
            if best is None or cost < best["cost"]:
                best = sol
            # more pillars rarely get cheaper once feasible — test one more then stop
            if n_p >= 2 and best is not sol:
                break
        elif best is None and n_p == cfg["max_pillars"]:
            best = sol
    if best is None:
        best = sol
    best["config"] = {k: v for k, v in cfg.items() if not k.startswith("_")}
    best["installation_notes"] = installation_notes(pts)
    best["total_W"] = sum(q["W"] for q in pts)
    best["n_poles"] = len(pts)
    for p in best["pillars"]:
        I3 = p["load_W"] / (3 * cfg["U0"] * cfg["pf"])
        p["Ib"] = I3
        p["main_In"] = next((r for r in RATINGS if r >= I3 * 1.25), RATINGS[-1])
    best["sld"] = sld(best, cfg)
    return best


def sld(sol, cfg):
    """Single-line diagram description used by the drawing code."""
    out = []
    for p in sol["pillars"]:
        fe = [f for f in sol["feeders"] if f["pillar"] == p["id"]]
        out.append(dict(
            pillar=p["id"], supply="%s %.0f/%.0f V 50 Hz" % (cfg["system"], cfg["U0"], cfg["Un"]),
            main="Main switch-disconnector %d A, 4P" % max(32, p["main_In"]),
            meter="kWh meter (CT or direct)", spd="SPD Type 2, Uc 275 V, In 20 kA (IEC 61643-11)",
            control="Contactor + astronomical timer / photocell; optional CMS gateway",
            earth="Earth electrode at pillar; %s" % ("RCD %.0f mA per feeder" % (cfg["Idn"] * 1000)
                                                     if cfg["system"].upper().startswith("TT") else "PE to every column"),
            feeders=[dict(id=f["id"], device="%s%d" % (cfg["device"].upper().replace("GG", "gG "), f["In"]),
                          cable="%s %s 5×%g mm² %s" % (cfg["material"], cfg["insulation"], f["size"],
                                                      {"D1": "in duct", "D2": "direct buried"}[cfg["method"]]),
                          length=round(f["length"], 1), n=len(f["poles"]),
                          load_W=round(sum(q["W"] for q in f["poles"]), 0),
                          du=round(f["du_max"], 2), ok=f["ok"]) for f in fe]))
    return out
