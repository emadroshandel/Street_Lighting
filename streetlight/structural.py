# Street Lighting — road lighting design to EN 13201, CIE 140 and IES RP-8.
# Copyright (C) 2026 Emad Roshandel — GPL-3.0-or-later (see LICENSE)
"""Lighting column pre-design to EN 40-3-1:2013 (loads) and EN 40-3-3:2013 (verification).

Loads, EN 40-3-1:
    q(z) = delta * beta * f * ce(z) * q(10)                                    (1)
    q(10) = 0.5 rho Cs^2 Vref^2,  Cs = sqrt(0.92) for a 25-year return period    (2), 5.2.2
    delta = 1 - 0.01 h                                                         5.2.3
    beta (metal) = 1.00240 - 0.00500 T^4 + 0.05144 T^3 - 0.22793 T^2 + 0.67262 T   5.2.4
    ce(z) = cr^2 + 7 kr cr,  cr = kr ln(max(z, zmin) / z0), Table 3            5.2.6
    shape coefficient c from Figure 3 with Re = V D / nu,
        V = (1 / Cs) sqrt(q(z) / (0.5 rho delta beta)),  nu = 15.1e-6 m2/s      5.3
    luminaire: c = 1.0 without wind-tunnel data; its weight acts 0.4 x its
    length beyond the bracket end; sections of at most 2 m.                     5.3.4, 6.1.4, 6.2.1
Natural period T: Rayleigh's method on the tapered shaft with the head mass.

Verification, EN 40-3-3 (closed circular steel sections):
    design loads gamma_f (Table 1): class A wind 1.4, dead 1.2; class B 1.2 / 1.2
    Mup = fy phi1 Zp / gamma_m,  Zp = 4 R^2 t,  phi1 (Figure 2) from
        eps = (R/t) sqrt(fy/E): 1 for eps <= 0.8, (0.8/eps)^0.35 to 2.0          (2)
    Tu = fy phi2 pi R^2 t / gamma_m,  phi2 = 0.474 E / (fy (R/t)^1.5) <= 1     (3)
    gamma_m = 1.05 for steel with elongation > 15 % (Table 2)
    door opening (unreinforced, 5.6.2.2): Mux, Muy with phi3, Zpn, Zpy and
        Tu with phi4, phi5 (Figure 4 expression); checked at its lower edge
    acceptance: Mp/Mup + Tp/Tu <= 1 (11); at the door Mx/Mux + My/Muy + Tp/Tu <= 1 (10)
    deflection (characteristic loads): flexure of shaft and bracket plus the
        torsional rotation times the projection, <= 0.04 / 0.06 / 0.10 (h + w)
        for classes 1 / 2 / 3 (Table 4); vertical <= 0.025 w (6.5.2)

Foundation: planted depth by Broms' method and by the PD 6547:2004+A1:2009
ground-factor method (Mg = G D P^3 / 10 >= 1.25 x moment about P/2); the larger
governs.  This is a pre-design; the column supplier's verification governs.
"""
from __future__ import annotations

import math

# EN 40-3-1:2013 Table 1 / Table 3: kr, z0 (m), zmin (m), description.  "0" (open sea, EN 1991-1-4)
# is not an EN 40 category and is taken as category I.
TERRAIN = {
    "I": (0.17, 0.01, 2.0, "Rough open sea, lakeshore with 5 km fetch, smooth flat country"),
    "II": (0.19, 0.05, 4.0, "Farmland with hedges, occasional small structures, houses or trees"),
    "III": (0.22, 0.30, 8.0, "Suburban or industrial areas and permanent forests"),
    "IV": (0.24, 1.00, 16.0, "Urban areas, at least 15 % covered by buildings over 15 m"),
}
TERRAIN_ALIAS = {"0": "I"}
DEFAULT_TERRAIN = "II"           # EN 40-3-1 5.2.6 NOTE 2

# EN 40-3-1:2013 5.2.2: for the usual 25-year return period of lighting columns Cs = sqrt(0.92)
CS_25Y = 0.92 ** 0.5
NU_AIR = 15.1e-6                 # 5.3, kinematic viscosity at 20 deg C

STEEL = {"S235": 235.0, "S275": 275.0, "S355": 355.0}
E_STEEL = 210e9                  # EN 40-3-3 Table 3
G_STEEL = 81e9
RHO_STEEL = 7850.0
GAMMA_M_STEEL = 1.05             # EN 40-3-3 Table 2, elongation > 15 % (S235..S355)
LOAD_CLASS = {"A": (1.4, 1.2), "B": (1.2, 1.2)}    # EN 40-3-3 Table 1: (wind, dead)
DEFL_CLASS = {1: 0.04, 2: 0.06, 3: 0.10}           # EN 40-3-3 Table 4, x (h + w)
# PD 6547 Table 2: ground factor G (kN/m2 per m)
GROUND_G = {"good": 630.0, "average": 390.0, "poor": 230.0}


def _terrain(cat):
    cat = TERRAIN_ALIAS.get(str(cat), str(cat))
    if cat not in TERRAIN:
        raise ValueError("Unknown terrain category %s (EN 40-3-1 uses I to IV)." % cat)
    return cat


def ce(z, cat=DEFAULT_TERRAIN):
    """Exposure coefficient, EN 40-3-1:2013 5.2.6 (Table 2 / Table 3)."""
    kr, z0, zmin, _ = TERRAIN[_terrain(cat)]
    cr = kr * math.log(max(z, zmin) / z0)
    return cr * cr + 7.0 * kr * cr


def beta_metal(T):
    """Dynamic factor for metal columns, EN 40-3-1:2013 5.2.4 NOTE (Figure 1, curve 1):

        beta = 1.00240 - 0.00500 T^4 + 0.05144 T^3 - 0.22793 T^2 + 0.67262 T,  0 <= T <= 3.5 s

    (beta = 1.29 at T = 0.5 s, 1.49 at 1 s, 1.65 at 1.5 s, 2.03 at 3.5 s as read from Figure 1.)
    """
    T = min(max(T, 0.0), 3.5)
    return 1.00240 - 0.00500 * T ** 4 + 0.05144 * T ** 3 - 0.22793 * T ** 2 + 0.67262 * T


def shape_coefficient(Re, section="circular"):
    """EN 40-3-1:2013 Figure 3 (Re in absolute units; the figure's axis is Re x 10^-5).

    circular (curve 3): 1.2 up to 2e5, 0.5 at 4e5, 0.6 at 1e6 and above.
    octagonal r/D < 0.075 (curve 1): 1.45 up to 2.2e5, 1.3 from 3e5.
    octagonal r/D >= 0.075 (curve 2): 1.29 up to 2e5, 1.1 from 7e5.
    """
    x = Re / 1e5
    pts = {"circular": [(0, 1.2), (2, 1.2), (4, 0.5), (10, 0.6)],
           "octagonal_sharp": [(0, 1.45), (2.2, 1.45), (3, 1.3), (10, 1.3)],
           "octagonal_round": [(0, 1.29), (2, 1.29), (7, 1.1), (10, 1.1)]}[section]
    if x >= pts[-1][0]:
        return pts[-1][1]
    for (x0, c0), (x1, c1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            return c0 + (c1 - c0) * (x - x0) / (x1 - x0)
    return pts[0][1]


def shape_circular(V, D):
    """Kept for compatibility: shape coefficient of a circular section at wind speed V (m/s)."""
    Re = V * D / NU_AIR
    return shape_coefficient(Re, "circular"), Re


def section_props(D, t):
    """Circular hollow section: area, I, W (m2, m4, m3)."""
    Di = max(D - 2 * t, 0.0)
    A = math.pi / 4 * (D ** 2 - Di ** 2)
    I = math.pi / 64 * (D ** 4 - Di ** 4)
    return A, I, I / (D / 2)


def phi1(eps, section="circular"):
    """EN 40-3-3:2013 Figure 2; None when eps > 2 (section too slender for the standard)."""
    if eps <= 0.8:
        return 1.0
    if eps > 2.0:
        return None
    p = (0.8 / eps) ** 0.35
    if section != "circular" and eps > 1.53:
        p = min(p, 0.81 - 0.3 * (eps - 1.5) ** 0.9)
    return p


def closed_resistance(D, t, fy, gm=GAMMA_M_STEEL):
    """EN 40-3-3 5.6.2.1, circular: (Mup, Tu) in N m, plus the factors used."""
    R, tt = (D - t) / 2 * 1e3, t * 1e3                 # mean radius, thickness in mm
    E = E_STEEL / 1e6
    eps = (R / tt) * math.sqrt(fy / E)
    p1 = phi1(eps)
    p2 = min(0.474 * E / (fy * (R / tt) ** 1.5), 1.0)
    Zp = 4 * R * R * tt
    Mup = fy * (p1 or 0.0) * Zp / (1e3 * gm)
    Tu = fy * p2 * math.pi * R * R * tt / (1e3 * gm)
    return Mup, Tu, dict(R=R, eps=eps, phi1=p1, phi2=p2, Zp=Zp)


def phi5(theta_deg, R_over_L):
    """EN 40-3-3:2013 Figure 4 (closed-form NOTE)."""
    th = math.radians(theta_deg)
    a = 1 + 2.15 * math.tan(th) + 0.85 * R_over_L
    return 10 * math.cos(th / 2) ** 2 / (1 + 1.73 * math.tan(th)) * a / (a + 3.8 * R_over_L ** 2)


def door_resistance(D, t, fy, a=0.5, b=0.12, N=0.02, gm=GAMMA_M_STEEL):
    """EN 40-3-3 5.6.2.2, unreinforced door in a circular section.

    a, b, N: overall length, width and corner radius of the opening (m).
    Returns (Mux, Muy, Tu) in N m and the factors used.
    """
    R, tt = (D - t) / 2 * 1e3, t * 1e3
    E = E_STEEL / 1e6
    L = a * 1e3 - 0.43 * min(N, b / 2) * 1e3
    theta = math.degrees(math.asin(min(1.0, b * 1e3 / 2 / R)))
    _, _, f = closed_resistance(D, t, fy, gm)
    p3 = min(tt * tt * E / (tt * tt * E + 0.07 * R * L * fy), f["phi1"] or 0.0)
    p4 = min(tt * tt * E / (tt * tt * E + 0.035 * R * L * fy), f["phi2"])
    p5 = phi5(theta, R / L)
    F, g, th = 2.0, 1.0, math.radians(theta)
    Zpn = 2 * F * R * R * tt * math.cos(th / 2) * (1 - math.sin(th / 2))
    Zpy = F * R * R * tt * (1 + math.cos(th))
    Mux = fy * g * p3 * Zpn / (1e3 * gm)
    Muy = fy * g * p3 * Zpy / (1e3 * gm)
    Tu = fy * g * p4 * p5 * R ** 3 * tt / (1e3 * gm * L)
    return Mux, Muy, Tu, dict(theta=theta, L=L, phi3=p3, phi4=p4, phi5=p5, Zpn=Zpn, Zpy=Zpy)


def column_check(h, overhang, lum_weight, lum_wind_area, n_heads=1, Vref=27.0, terrain=DEFAULT_TERRAIN,
                 Cs=CS_25Y, topo=1.0, rho=1.25, D_top=0.076, taper=0.012, t=0.004, grade="S355",
                 bracket_d=0.06, defl_class=2, load_class="A", lum_length=0.6, door=None):
    """EN 40-3-1 loads and EN 40-3-3 verification of a tapered circular steel column."""
    terrain = _terrain(terrain)
    gw, gd = LOAD_CLASS[load_class]
    fy = STEEL.get(grade, 355.0)
    door = dict(dict(z=0.6, a=0.5, b=0.12, N=0.02), **(door or {}))
    q10 = 0.5 * rho * Cs ** 2 * Vref ** 2
    D_base = D_top + taper * h
    n = max(10, int(math.ceil(h / 0.5)))              # sections of 0.5 m (EN 40-3-1 6.2.1: <= 2 m)
    dz = h / n
    zs = [(i + 0.5) * dz for i in range(n)]
    Dz = [D_base - taper * z for z in zs]
    Iz = [section_props(d, t)[1] for d in Dz]
    m_sec = [section_props(d, t)[0] * dz * RHO_STEEL for d in Dz]
    m_head = n_heads * lum_weight + RHO_STEEL * section_props(bracket_d, 0.003)[0] * overhang * n_heads

    def tip_deflections(forces, tip_force=0.0):
        """Horizontal deflection at each section centre and at the top for loads at section centres."""
        M = []
        for i, z in enumerate(zs):
            M.append(sum(F * (zj - z) for F, zj in zip(forces[i:], zs[i:])) + tip_force * (h - z))
        # curvature and double integration from the fixed base
        slope, y, ys = 0.0, 0.0, []
        for i in range(n):
            k = M[i] / (E_STEEL * Iz[i])
            slope += k * dz
            y += slope * dz
            ys.append(y)
        return ys, y + slope * dz / 2

    # natural period by Rayleigh: lateral load = weights
    w = [m * 9.81 for m in m_sec]
    ys, ytop = tip_deflections(w, m_head * 9.81)
    num = sum(m * yy for m, yy in zip(m_sec, ys)) + m_head * ytop
    den = sum(m * yy * yy for m, yy in zip(m_sec, ys)) + m_head * ytop * ytop
    T = 2 * math.pi * math.sqrt(den / (9.81 * num)) if num > 0 else 0.0
    beta = beta_metal(T)
    delta = 1 - 0.01 * h
    qz = lambda z: delta * beta * topo * ce(z, terrain) * q10
    vz = lambda q: math.sqrt(q / (0.5 * rho * delta * beta)) / Cs       # EN 40-3-1 5.3
    # characteristic forces (N) per section, bracket and luminaire
    F_sec = []
    for z, d in zip(zs, Dz):
        q = qz(z)
        c = shape_coefficient(vz(q) * d / NU_AIR, "circular")
        F_sec.append(q * c * d * dz)
    qh = qz(h)
    cb = shape_coefficient(vz(qh) * bracket_d / NU_AIR, "circular")
    Fb = qh * cb * bracket_d * overhang * n_heads
    Fl = qh * 1.0 * lum_wind_area * n_heads                              # 5.3.4: c = 1.0
    F_head = Fb + Fl
    M_w = sum(F * z for F, z in zip(F_sec, zs)) + F_head * h
    F_tot = sum(F_sec) + F_head
    # dead load eccentricity (single-sided only): luminaire at w + 0.4 L, bracket at w / 2   (6.1.4)
    single = n_heads == 1
    W_lum, W_br = lum_weight * 9.81, RHO_STEEL * section_props(bracket_d, 0.003)[0] * overhang * 9.81
    M_dead = (W_lum * (overhang + 0.4 * lum_length) + W_br * overhang / 2) if single else 0.0
    # torsion from wind on a one-sided head: luminaire at w + L/2, bracket at w/2 (5.5.2 a: also for twins)
    T_char = Fl / n_heads * (overhang + 0.5 * lum_length) + Fb / n_heads * overhang / 2
    # design actions at the base and at the lower edge of the door
    Mb = gw * M_w + gd * M_dead
    Tp = gw * T_char
    zd = door["z"]
    M_door_w = sum(F * (z - zd) for F, z in zip(F_sec, zs) if z > zd) + F_head * (h - zd)
    Md = gw * M_door_w + gd * M_dead
    Mup, Tu, f = closed_resistance(D_base, t, fy)
    D_door = D_base - taper * zd
    Mux, Muy, Tud, fd = door_resistance(D_door, t, fy, door["a"], door["b"], door["N"])
    slender = f["phi1"] is None
    util_base = (Mb / Mup + Tp / Tu) if not slender else float("inf")
    # door position relative to the bracket is unknown: the weakest axis (5.1 b)
    util_door = (Md / min(Mux, Muy) + Tp / Tud) if not slender and min(Mux, Muy) > 0 else float("inf")
    util = max(util_base, util_door)
    # serviceability: characteristic loads (gamma = 1), flexure + torsion x projection (6.4.1.2)
    _, d_flex = tip_deflections(F_sec, F_head)
    Ib = section_props(bracket_d, 0.003)[1]
    d_bracket = (Fl / n_heads) * overhang ** 3 / (3 * E_STEEL * Ib) if overhang > 0 else 0.0
    rot = sum(T_char * dz / (G_STEEL * 2 * I) for I in Iz)
    defl = d_flex + d_bracket + rot * overhang
    lim = DEFL_CLASS.get(int(defl_class), 0.06) * (h + overhang)
    d_vert = (W_lum + W_br / 2) * overhang ** 3 / (3 * E_STEEL * Ib) if overhang > 0 else 0.0
    v_ok = overhang <= 0 or d_vert <= 0.025 * overhang
    A, I, W = section_props(D_base, t)
    notes = []
    if slender:
        notes.append("R/t too large: eps = %.2f > 2.0 is outside EN 40-3-3 Figure 2" % f["eps"])
    return dict(h=h, D_base=D_base, D_top=D_top, t=t, grade=grade, fy=fy, q10=q10, T=T, beta=beta,
                delta=delta, ce_h=ce(h, terrain), q_h=qh, terrain=terrain, load_class=load_class,
                F_total=F_tot, M_wind=M_w, M_dead=M_dead, M_design=Mb, T_design=Tp,
                Mup=Mup, Tu=Tu, util_base=util_base, M_door=Md, Mu_door=min(Mux, Muy), Tu_door=Tud,
                util_door=util_door, util=util, eps=f["eps"], phi1=f["phi1"], door=dict(door, **fd),
                sigma=Mb / W / 1e6, deflection=defl, defl_limit=lim, defl_parts=dict(
                    flexure=d_flex, bracket=d_bracket, torsion=rot * overhang),
                defl_ok=defl <= lim, defl_vertical=d_vert, defl_vertical_ok=v_ok,
                torsion=T_char, mass=sum(m_sec), ok=util <= 1.0 and defl <= lim and v_ok,
                H_base=F_tot, notes=notes)


def select_column(h, overhang, lum_weight, lum_wind_area, n_heads=1, **kw):
    """Lightest tapered tube that passes (thickness 3..6 mm, top 60..114 mm, taper 10..15 mm/m)."""
    best = None
    for t in (0.003, 0.004, 0.005, 0.006):
        for D_top in (0.060, 0.076, 0.089, 0.114):
            for taper in (0.010, 0.012, 0.015):
                r = column_check(h, overhang, lum_weight, lum_wind_area, n_heads, D_top=D_top, taper=taper,
                                 t=t, **kw)
                if r["ok"] and (best is None or r["mass"] < best["mass"]):
                    best = r
    if best is None:
        best = column_check(h, overhang, lum_weight, lum_wind_area, n_heads, D_top=0.114, taper=0.015,
                            t=0.006, **kw)
        best["note"] = "No standard tube passes — a heavier column, a reinforced door or a guyed support is needed."
    return best


def foundation_pd6547(H, M, D=0.6, quality="average", FS=1.25):
    """Planting depth P by PD 6547:2004+A1:2009 6.3: G D P^3 / 10 >= FS x (M + H P / 2), kN and m."""
    G = GROUND_G.get(quality, GROUND_G["average"])
    P = 0.5
    while P < 6.0:
        Mg = G * D * P ** 3 / 10.0
        Mo = (M + H * P / 2.0) / 1000.0
        if Mg >= FS * Mo:
            break
        P += 0.05
    P = math.ceil(P * 20) / 20.0
    return dict(depth=P, diameter=D, G=G, quality=quality, FS=FS,
                method="PD 6547 ground factor G = %.0f kN/m² per m (%s ground)" % (G, quality))


def foundation_broms(H, M, D=0.6, soil="cohesionless", phi=30.0, gamma=18.0, cu=50.0, FS=2.0):
    """Embedment depth of a short rigid pile (column planted in a bored concrete foundation).

    H (N) horizontal force at ground, M (N m) moment at ground.
    cohesionless: Hu = 0.5 gamma D L^3 Kp / (e + L)        (Broms 1964, free head)
    cohesive:     L = 1.5 D + f + g,  f = Hu / (9 cu D),  Mmax = Hu (e + 1.5 D + 0.5 f) = 2.25 cu D g^2
    """
    Hd, Md = FS * H, FS * M
    e = Md / max(Hd, 1e-9)
    if soil == "cohesive":
        cu_n = cu * 1000.0
        f = Hd / (9 * cu_n * D)
        Mmax = Hd * (e + 1.5 * D + 0.5 * f)
        g = math.sqrt(Mmax / (2.25 * cu_n * D))
        L = 1.5 * D + f + g
        method = "Broms (cohesive, cu = %.0f kPa)" % cu
    else:
        Kp = math.tan(math.radians(45 + phi / 2)) ** 2
        g_n = gamma * 1000.0
        L = 0.3
        while L < 6.0:
            Hu = 0.5 * g_n * D * L ** 3 * Kp / (e + L)
            if Hu >= Hd:
                break
            L += 0.05
        method = "Broms (cohesionless, φ = %.0f°, Kp = %.2f)" % (phi, Kp)
    L = math.ceil(L * 20) / 20.0
    vol = math.pi / 4 * D ** 2 * (L + 0.1)
    return dict(depth=L, diameter=D, volume=vol, method=method, FS=FS, H=H, M=M)


def foundation_block(H, M, W_col, B=0.8, gamma_c=24.0, gamma_s=18.0, phi=30.0, FS=1.5):
    """Square concrete block: smallest depth giving FS against overturning
    (self weight about the toe plus passive resistance on the front face)."""
    Kp = math.tan(math.radians(45 + phi / 2)) ** 2
    D = 0.6
    while D < 3.0:
        Wb = gamma_c * 1000 * B * B * D
        Mr = (Wb + W_col) * B / 2 + 0.5 * gamma_s * 1000 * Kp * D ** 2 * B * D / 3
        Mo = M + H * D
        if Mr >= FS * Mo:
            break
        D += 0.05
    D = math.ceil(D * 20) / 20.0
    return dict(B=B, depth=D, volume=B * B * D, FS=FS, method="Block overturning with passive earth pressure")


def design_pole(H, overhang, lum_weight=10.0, lum_wind_area=0.12, n_heads=1, wind=None, soil=None,
                lum_length=0.6):
    if not (2.0 <= float(H) <= 30.0):
        raise ValueError("Column height must lie between 2 and 30 m (EN 40 lighting columns).")
    if float(overhang) < 0 or float(lum_weight) < 0 or float(lum_wind_area) < 0:
        raise ValueError("Bracket length, luminaire weight and wind area cannot be negative.")
    wind = dict(Vref=27.0, terrain=DEFAULT_TERRAIN, Cs=CS_25Y, topo=1.0, grade="S355", defl_class=2,
                load_class="A") | {k: v for k, v in (wind or {}).items() if v not in (None, "")}
    soil = dict(type="cohesionless", phi=30.0, gamma=18.0, cu=50.0, D=0.6, quality="average") | \
        {k: v for k, v in (soil or {}).items() if v not in (None, "")}
    if not (10.0 <= float(wind["Vref"]) <= 70.0):
        raise ValueError("Reference wind speed must lie between 10 and 70 m/s.")
    if wind.get("load_class") not in LOAD_CLASS:
        raise ValueError("Load class must be A or B (EN 40-3-3 Table 1).")
    col = select_column(H, overhang, lum_weight, lum_wind_area, n_heads, Vref=float(wind["Vref"]),
                        terrain=wind["terrain"], Cs=float(wind["Cs"]), topo=float(wind["topo"]),
                        grade=wind["grade"], defl_class=int(wind["defl_class"]), load_class=wind["load_class"],
                        lum_length=lum_length, door=wind.get("door"))
    M = col["M_wind"] + col["M_dead"]
    Hf = col["F_total"]
    broms = foundation_broms(Hf, M, D=float(soil["D"]), soil=soil["type"], phi=float(soil["phi"]),
                             gamma=float(soil["gamma"]), cu=float(soil["cu"]))
    pd = foundation_pd6547(Hf, M, D=float(soil["D"]), quality=soil.get("quality", "average"))
    fnd = dict(broms) if broms["depth"] >= pd["depth"] else dict(pd)
    fnd["alternatives"] = [dict(method=broms["method"], depth=broms["depth"]),
                           dict(method=pd["method"], depth=pd["depth"])]
    blk = foundation_block(Hf, M, col["mass"] * 9.81, phi=float(soil["phi"]), gamma_s=float(soil["gamma"]))
    return dict(column=col, foundation=fnd, block=blk, wind=wind, soil=soil,
                anchor_note="Anchor bolts / base plate per the column supplier; planted depth is the "
                            "alternative for a root-mounted column.")
